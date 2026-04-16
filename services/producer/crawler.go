package main

import (
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"

	"golang.org/x/net/html"
)

// PageMetadata holds the extracted info from a crawled page
type PageMetadata struct {
	URL             string `json:"url"`
	Domain          string `json:"domain"`
	Title           string `json:"title"`
	MetaDescription string `json:"meta_description"`
	CrawledAt       string `json:"crawled_at"`
	JobID           string `json:"job_id,omitempty"`
	Material        string `json:"material,omitempty"`
	SourceLabel     string `json:"source_label,omitempty"`
}

// crawlJob is queued from Kafka (gateway) before crawling.
type crawlJob struct {
	URL         string
	JobID       string
	Material    string
	SourceLabel string
}

// crawlURL fetches a page and extracts title + meta description
func crawlURL(rawURL string) (*PageMetadata, error) {
	client := &http.Client{Timeout: 10 * time.Second}

	resp, err := client.Get(rawURL)
	if err != nil {
		return nil, fmt.Errorf("GET %s: %w", rawURL, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("GET %s returned status %d", rawURL, resp.StatusCode)
	}

	// parse the HTML
	doc, err := html.Parse(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("parsing HTML from %s: %w", rawURL, err)
	}

	title := extractTitle(doc)
	description := extractMetaDescription(doc)

	// pull domain from URL
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return nil, fmt.Errorf("parsing URL %s: %w", rawURL, err)
	}

	return &PageMetadata{
		URL:             rawURL,
		Domain:          parsed.Host,
		Title:           title,
		MetaDescription: description,
		CrawledAt:       time.Now().UTC().Format(time.RFC3339),
	}, nil
}

// extractTitle walks the HTML tree looking for <title> text
func extractTitle(n *html.Node) string {
	if n.Type == html.ElementNode && n.Data == "title" {
		// grab the text content inside <title>
		if n.FirstChild != nil {
			return strings.TrimSpace(n.FirstChild.Data)
		}
		return ""
	}
	// recurse into children
	for c := n.FirstChild; c != nil; c = c.NextSibling {
		if result := extractTitle(c); result != "" {
			return result
		}
	}
	return ""
}

// extractMetaDescription finds <meta name="description" content="...">
func extractMetaDescription(n *html.Node) string {
	if n.Type == html.ElementNode && n.Data == "meta" {
		isDescription := false
		content := ""
		for _, attr := range n.Attr {
			if strings.EqualFold(attr.Key, "name") && strings.EqualFold(attr.Val, "description") {
				isDescription = true
			}
			if strings.EqualFold(attr.Key, "content") {
				content = attr.Val
			}
		}
		if isDescription {
			return content
		}
	}
	for c := n.FirstChild; c != nil; c = c.NextSibling {
		if result := extractMetaDescription(c); result != "" {
			return result
		}
	}
	return ""
}

// worker pulls crawl jobs from the channel, crawls them, and publishes results
func worker(id int, jobs <-chan crawlJob, producer *KafkaProducer) {
	for job := range jobs {
		log.Printf("[worker %d] crawling %s", id, job.URL)
		meta, err := crawlURL(job.URL)
		if err != nil {
			log.Printf("[worker %d] error crawling %s: %v", id, job.URL, err)
			continue
		}
		meta.JobID = job.JobID
		meta.Material = job.Material
		meta.SourceLabel = job.SourceLabel
		log.Printf("[worker %d] got title=%q from %s", id, meta.Title, job.URL)

		if err := producer.Publish(meta); err != nil {
			log.Printf("[worker %d] failed to publish metadata for %s: %v", id, job.URL, err)
		}
	}
	log.Printf("[worker %d] done", id)
}
