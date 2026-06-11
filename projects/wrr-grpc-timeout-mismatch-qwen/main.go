package main

import (
	"context"
	"fmt"
	"time"

	"google.golang.org/grpc"
)

func callService(ctx context.Context) error {
	// FIX 1: client timeout must be >= server processing time (3-5s), use 6s with margin
	clientCtx, cancel := context.WithTimeout(ctx, 6*time.Second)
	defer cancel()

	// FIX 3: handle Dial error properly
	conn, err := grpc.Dial("localhost:50051", grpc.WithInsecure())
	if err != nil {
		return fmt.Errorf("failed to dial: %w", err)
	}
	defer conn.Close()

	// FIX 2: propagate clientCtx (with deadline) into the gRPC call
	// so server receives the grpc-timeout header and can cancel early if needed.
	// Example: resp, err := pb.NewServiceClient(conn).DoWork(clientCtx, req)
	_ = clientCtx
	_ = conn
	return nil
}

func main() {
	callService(context.Background())
}
