package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	_ "github.com/lib/pq"
	"github.com/redis/go-redis/v9"
	"github.com/segmentio/kafka-go"
)

// global clients shared across handlers
var (
	db          *sql.DB
	rdb         *redis.Client
	kafkaWriter *kafka.Writer
)

func main() {
	// load config from env
	kafkaBrokers := strings.Split(getEnv("KAFKA_BROKERS", "localhost:9092"), ",")
	redisHost := getEnv("REDIS_HOST", "localhost:6379")
	dbHost := getEnv("DB_HOST", "localhost")
	dbPort := getEnv("DB_PORT", "5432")
	dbUser := getEnv("DB_USER", "postgres")
	dbPass := getEnv("DB_PASSWORD", "postgres")
	dbName := getEnv("DB_NAME", "pipeline")
	migrationsPath := getEnv("MIGRATIONS_PATH", "/app/migrations")

	// connect to postgres
	connStr := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		dbHost, dbPort, dbUser, dbPass, dbName)
	var err error
	db, err = sql.Open("postgres", connStr)
	if err != nil {
		log.Fatalf("failed to connect to postgres: %v", err)
	}
	db.SetMaxOpenConns(20)
	db.SetConnMaxLifetime(5 * time.Minute)
	log.Println("connected to postgres")

	// run migrations (idempotent)
	if err := runMigrations(db, migrationsPath); err != nil {
		log.Fatalf("migrations failed: %v", err)
	}
	log.Println("migrations applied")

	// outbox relay: drains domain_events into Kafka at-least-once.
	// Runs as a goroutine in the gateway process for deploy simplicity; can be
	// extracted into its own service later with zero code change (just point it
	// at the same Postgres + Kafka).
	startOutboxRelay(context.Background(), db, kafkaBrokers, 1*time.Second)

	// connect to redis
	rdb = redis.NewClient(&redis.Options{
		Addr: redisHost,
	})
	if err := rdb.Ping(context.Background()).Err(); err != nil {
		log.Printf("warning: redis not reachable: %v", err)
	} else {
		log.Println("connected to redis")
	}

	// set up kafka producer
	kafkaWriter = &kafka.Writer{
		Addr:                   kafka.TCP(kafkaBrokers...),
		Topic:                  "crawl-jobs",
		Balancer:               &kafka.LeastBytes{},
		BatchTimeout:           10 * time.Millisecond,
		AllowAutoTopicCreation: true,
	}
	log.Println("kafka writer ready")

	// set up router
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   corsOrigins(),
		AllowedMethods:   []string{"GET", "POST", "OPTIONS"},
		AllowedHeaders:   []string{"Content-Type"},
		AllowCredentials: true,
		MaxAge:           300,
	}))
	r.Use(resolveSession)

	// --- v1 routes (unauth, sentinel org_id=0) ---
	r.Get("/health", handleHealth)
	r.Get("/api/status", handleStatus)
	r.Post("/api/crawl", handleCrawl)
	r.Get("/api/results", handleResults)
	r.Get("/api/results/{id}", handleResultByID)

	// --- auth ---
	r.Post("/auth/magic-link", handleRequestMagicLink)
	r.Get("/auth/verify", handleVerifyMagicLink)
	r.Post("/auth/logout", handleLogout)

	// --- v2 routes (require session, tenant-scoped tx) ---
	r.Route("/api/v2", func(v2 chi.Router) {
		v2.Use(requireAuth)
		v2.Use(withTenantTx)
		v2.Get("/me", handleMe)
		v2.Get("/results", handleV2Results)
		v2.Post("/test/seed", handleV2TestSeed)

		// catalog (browse global library)
		v2.Get("/catalog/materials", handleV2CatalogMaterials)
		v2.Get("/catalog/products", handleV2CatalogProducts)
		v2.Get("/catalog/indicators", handleV2CatalogIndicators)

		// tenant overlay (enable, override, private)
		v2.Post("/tenant/materials/enable", handleV2TenantEnableMaterial)
		v2.Post("/tenant/materials", handleV2TenantCreateMaterial)
		v2.Post("/tenant/indicators/enable", handleV2TenantEnableIndicator)
		v2.Post("/tenant/indicators/override", handleV2TenantOverrideIndicator)
		v2.Post("/tenant/indicators", handleV2TenantCreateIndicator)

		// resolved tenant view (composer applies precedence)
		v2.Get("/me/materials", handleV2MeMaterials)
		v2.Get("/me/indicators", handleV2MeIndicators)

		// goals
		v2.Post("/goals", handleV2GoalsCreate)
		v2.Get("/goals", handleV2GoalsList)
		v2.Get("/goals/{id}", handleV2GoalDetail)
		v2.Delete("/goals/{id}", handleV2GoalDelete)
		v2.Post("/goals/{id}/indicators", handleV2GoalAddIndicator)
		v2.Delete("/goals/{id}/indicators/{linkId}", handleV2GoalRemoveIndicator)

		// insights + traceability
		v2.Post("/insights", handleV2InsightCreate)
		v2.Get("/insights", handleV2InsightsList)
		v2.Get("/insights/{id}", handleV2InsightDetail)
		v2.Get("/me/briefing", handleV2MeBriefing)

		// indicator composer + reading seed
		v2.Get("/indicators/{code}/latest", handleV2IndicatorLatest)
		v2.Post("/test/indicator/reading", handleV2TestIndicatorReading)

		// saga observability
		v2.Get("/workflows", handleV2WorkflowsList)
	})

	// Copilot proxy lives OUTSIDE the tenant-tx group (it's HTTP→HTTP, not DB).
	r.With(requireAuth).Post("/api/v2/copilot/converse", handleV2CopilotConverse)

	r.NotFound(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"error":"not found"}`))
	})

	log.Println("gateway listening on :8080")
	if err := http.ListenAndServe(":8080", r); err != nil {
		log.Fatalf("server error: %v", err)
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// corsOrigins parses CORS_ALLOWED_ORIGINS (comma-separated). Default for local
// dev: nginx-frontend at :3000 + dev server. Production should override.
func corsOrigins() []string {
	v := getEnv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
	parts := strings.Split(v, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if s := strings.TrimSpace(p); s != "" {
			out = append(out, s)
		}
	}
	return out
}
