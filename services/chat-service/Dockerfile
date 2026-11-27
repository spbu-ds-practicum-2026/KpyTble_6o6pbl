FROM golang:1.27.4-alpine3.24 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -o /out/chat ./cmd/chat \
    && CGO_ENABLED=0 go build -trimpath -o /out/chat-migrate ./cmd/chat-migrate \
    && CGO_ENABLED=0 go build -trimpath -o /out/chat-web ./cmd/chat-web

FROM alpine:3.24
RUN apk add --no-cache ca-certificates \
    && addgroup -S chat && adduser -S -G chat chat
WORKDIR /app
COPY --from=build /out/chat /out/chat-migrate /out/chat-web ./
USER chat
ENV HTTP_ADDR=0.0.0.0:6767
EXPOSE 6767
CMD ["/app/chat"]
