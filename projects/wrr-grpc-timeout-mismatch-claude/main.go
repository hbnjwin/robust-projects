package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func callService(ctx context.Context) error {
	// FIX: client timeout must cover server's max processing time (3-5s) with margin
	clientCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	conn, err := grpc.Dial("localhost:50051", grpc.WithInsecure())
	if err != nil {
		return fmt.Errorf("failed to connect: %w", err)
	}
	defer conn.Close()

	// Use clientCtx for the RPC call so the deadline propagates to the server.
	// If the deadline is exceeded, the server also receives cancellation and
	// can stop early instead of doing wasted work.
	_ = clientCtx // pass clientCtx to the actual RPC stub call, e.g.:
	// resp, err := pb.NewMyServiceClient(conn).MyMethod(clientCtx, req)

	if err != nil {
		if s, ok := status.FromError(err); ok && s.Code() == codes.DeadlineExceeded {
			return fmt.Errorf("rpc timed out: %w", err)
		}
		return fmt.Errorf("rpc failed: %w", err)
	}
	return nil
}

func main() {
	if err := callService(context.Background()); err != nil {
		log.Fatalf("callService error: %v", err)
	}
}
