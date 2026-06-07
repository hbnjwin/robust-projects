package main

import (
	"context"
	"fmt"
	"time"

	"google.golang.org/grpc"
)

func callService(ctx context.Context) error {
	// BUG: client timeout shorter than server processing time
	clientCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	conn, _ := grpc.Dial("localhost:50051", grpc.WithInsecure())
	defer conn.Close()

	// Server takes 3-5s to process, but client times out at 2s
	// Server still completes and logs success, but client already returned error
	_ = clientCtx
	return fmt.Errorf("context deadline exceeded")
}

func main() {
	callService(context.Background())
}
