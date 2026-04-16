FROM --platform=linux/amd64 golang:1.25-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o gateway .

FROM --platform=linux/amd64 alpine:3.19
RUN apk --no-cache add ca-certificates wget
WORKDIR /app
COPY --from=builder /app/gateway .
COPY --from=builder /app/migrations ./migrations
EXPOSE 8080
CMD ["./gateway"]
