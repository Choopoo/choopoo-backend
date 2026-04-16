package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	KafkaBrokers []string
	CrawlTopic   string
	OutputTopic  string
	Concurrency  int
	Mode         string   // "consumer" or "standalone"
	SeedURLs     []string // only used in standalone mode
}

func loadConfig() Config {
	brokers := os.Getenv("KAFKA_BROKERS")
	if brokers == "" {
		brokers = "localhost:9092"
	}

	crawlTopic := os.Getenv("CRAWL_TOPIC")
	if crawlTopic == "" {
		crawlTopic = "crawl-jobs"
	}

	outputTopic := os.Getenv("OUTPUT_TOPIC")
	if outputTopic == "" {
		outputTopic = "page-metadata"
	}

	concurrency := 10
	if val := os.Getenv("CONCURRENCY"); val != "" {
		if n, err := strconv.Atoi(val); err == nil && n > 0 {
			concurrency = n
		}
	}

	mode := os.Getenv("MODE")
	if mode == "" {
		mode = "standalone"
	}

	var seeds []string
	if raw := os.Getenv("SEED_URLS"); raw != "" {
		for _, u := range strings.Split(raw, ",") {
			u = strings.TrimSpace(u)
			if u != "" {
				seeds = append(seeds, u)
			}
		}
	}

	return Config{
		KafkaBrokers: strings.Split(brokers, ","),
		CrawlTopic:   crawlTopic,
		OutputTopic:  outputTopic,
		Concurrency:  concurrency,
		Mode:         mode,
		SeedURLs:     seeds,
	}
}

func main() {
	cfg := loadConfig()
	log.Printf("starting producer service in %s mode (concurrency=%d)", cfg.Mode, cfg.Concurrency)

	// kafka producer for publishing crawl results
	producer := newKafkaProducer(cfg.KafkaBrokers, cfg.OutputTopic)
	defer producer.Close()

	// channel-based worker pool
	jobChan := make(chan crawlJob, cfg.Concurrency*2)

	// spin up worker goroutines
	for i := 0; i < cfg.Concurrency; i++ {
		go worker(i, jobChan, producer)
	}

	// health check endpoint
	go func() {
		http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
			fmt.Fprintln(w, "ok")
		})
		log.Println("health check server listening on :8080")
		if err := http.ListenAndServe(":8080", nil); err != nil {
			log.Fatalf("health server error: %v", err)
		}
	}()

	// pick mode
	switch cfg.Mode {
	case "consumer":
		log.Printf("consuming from topic %s", cfg.CrawlTopic)
		consumeFromKafka(cfg.KafkaBrokers, cfg.CrawlTopic, jobChan)
	case "standalone":
		if len(cfg.SeedURLs) == 0 {
			log.Fatal("standalone mode requires SEED_URLS env var")
		}
		log.Printf("crawling %d seed URLs", len(cfg.SeedURLs))
		for _, u := range cfg.SeedURLs {
			jobChan <- crawlJob{URL: u}
		}
		close(jobChan)
	default:
		log.Fatalf("unknown MODE: %s (expected consumer or standalone)", cfg.Mode)
	}

	// in standalone mode, workers finish when channel is closed
	// in consumer mode, consumeFromKafka blocks forever
	if cfg.Mode == "standalone" {
		// give workers a moment — simple approach for a course project
		select {}
	}
}
