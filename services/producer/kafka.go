package main

import (
	"context"
	"encoding/json"
	"log"
	"net/url"

	"github.com/segmentio/kafka-go"
)

// KafkaProducer wraps a kafka writer for publishing page metadata
type KafkaProducer struct {
	writer *kafka.Writer
}

func newKafkaProducer(brokers []string, topic string) *KafkaProducer {
	w := &kafka.Writer{
		Addr:                   kafka.TCP(brokers...),
		Topic:                  topic,
		Balancer:               &kafka.Hash{}, // partition by key (domain)
		AllowAutoTopicCreation: true,
	}
	return &KafkaProducer{writer: w}
}

// Publish sends page metadata to kafka, keyed by domain
func (p *KafkaProducer) Publish(meta *PageMetadata) error {
	data, err := json.Marshal(meta)
	if err != nil {
		return err
	}

	msg := kafka.Message{
		Key:   []byte(meta.Domain),
		Value: data,
	}

	err = p.writer.WriteMessages(context.Background(), msg)
	if err != nil {
		return err
	}
	log.Printf("published metadata for %s to kafka", meta.URL)
	return nil
}

func (p *KafkaProducer) Close() {
	if err := p.writer.Close(); err != nil {
		log.Printf("error closing kafka producer: %v", err)
	}
}

// crawlKafkaPayload matches the gateway JSON for crawl-jobs topic.
type crawlKafkaPayload struct {
	JobID       string `json:"job_id"`
	URL         string `json:"url"`
	Material    string `json:"material"`
	SourceLabel string `json:"source_label"`
}

// consumeFromKafka reads crawl jobs from the crawl-jobs topic and feeds them
// into the worker pool channel. This blocks forever.
func consumeFromKafka(brokers []string, topic string, jobChan chan<- crawlJob) {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  brokers,
		Topic:    topic,
		GroupID:  "producer-crawlers",
		MinBytes: 1,
		MaxBytes: 10e6, // 10MB
	})
	defer reader.Close()

	log.Printf("kafka consumer started on topic %s", topic)

	for {
		msg, err := reader.ReadMessage(context.Background())
		if err != nil {
			log.Printf("error reading from kafka: %v", err)
			continue
		}

		var payload crawlKafkaPayload
		if err := json.Unmarshal(msg.Value, &payload); err != nil || payload.URL == "" {
			log.Printf("skipping invalid crawl message: %s", string(msg.Value))
			continue
		}

		parsed, err := url.Parse(payload.URL)
		if err != nil || parsed.Scheme == "" {
			log.Printf("skipping invalid URL from kafka: %s", string(msg.Value))
			continue
		}

		log.Printf("received crawl job: %s", payload.URL)
		jobChan <- crawlJob{
			URL:         payload.URL,
			JobID:       payload.JobID,
			Material:    payload.Material,
			SourceLabel: payload.SourceLabel,
		}
	}
}
