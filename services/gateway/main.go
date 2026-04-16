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
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "OPTIONS"},
		AllowedHeaders:   []string{"Content-Type"},
		AllowCredentials: false,
		MaxAge:           300,
	}))

	// API routes first
	r.Get("/health", handleHealth)
	r.Get("/api/status", handleStatus)
	r.Post("/api/crawl", handleCrawl)
	r.Get("/api/results", handleResults)
	r.Get("/api/results/{id}", handleResultByID)

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
