package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"github.com/moby/moby/client"
	"os"
	"sort"
	"strings"
	"time"
)

func load() error {
	started := time.Now()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	docker, err := client.New(client.FromEnv)
	if err != nil {
		return err
	}
	defer docker.Close()
	result, err := docker.ContainerList(ctx, client.ContainerListOptions{All: true})
	if err != nil {
		return err
	}
	if len(result.Items) > 20000 {
		return fmt.Errorf("container limit exceeded (20,000)")
	}
	sort.Slice(result.Items, func(i, j int) bool {
		return strings.Join(result.Items[i].Names, ",") < strings.Join(result.Items[j].Names, ",")
	})
	var output bytes.Buffer
	fmt.Fprintf(&output, "%d containers · %.1f ms\n", len(result.Items), float64(time.Since(started).Microseconds())/1000)
	ids := make([]string, 0, len(result.Items))
	clean := func(s string) string {
		s = strings.NewReplacer("\t", " ", "\r", " ", "\n", " ").Replace(s)
		runes := []rune(s)
		if len(runes) > 512 {
			return string(runes[:512])
		}
		return s
	}
	for _, c := range result.Items {
		name := c.ID[:12]
		if len(c.Names) > 0 {
			name = strings.TrimPrefix(c.Names[0], "/")
		}
		fmt.Fprintf(&output, "%s\t%s\t%s\t%s\t%s\n", c.ID, clean(name), clean(c.Image), clean(string(c.State)), clean(c.Status))
		ids = append(ids, c.ID)
	}
	if output.Len() > 524288 {
		return fmt.Errorf("display response exceeds 512 KiB")
	}
	sort.Strings(ids)
	proof := fmt.Sprintf("Docker load: count=%d elapsed_ms=%.3f ids=%s\n", len(ids), float64(time.Since(started).Microseconds())/1000, strings.Join(ids, ","))
	if output.Len()+len(proof) > 524288 {
		return fmt.Errorf("display response and proof exceed 512 KiB")
	}
	fmt.Fprint(os.Stdout, proof)
	if path := os.Getenv("NATIVE_DOCKER_PROOF"); path != "" {
		file, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
		if err != nil {
			return err
		}
		_, err = file.WriteString(proof)
		file.Close()
		if err != nil {
			return err
		}
	}
	_, err = os.Stdout.Write(output.Bytes())
	return err
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "--configuration" {
		worker, err := os.Executable()
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		_ = json.NewEncoder(os.Stdout).Encode(map[string]string{"worker": worker, "host": os.Getenv("DOCKER_HOST"), "proof": os.Getenv("NATIVE_DOCKER_PROOF"), "certPath": os.Getenv("DOCKER_CERT_PATH"), "tlsVerify": os.Getenv("DOCKER_TLS_VERIFY")})
		return
	}
	if len(os.Args) == 5 {
		for key, value := range map[string]string{"DOCKER_HOST": os.Args[1], "NATIVE_DOCKER_PROOF": os.Args[2], "DOCKER_CERT_PATH": os.Args[3], "DOCKER_TLS_VERIFY": os.Args[4]} {
			if value != "" {
				_ = os.Setenv(key, value)
			}
		}
	}
	if err := load(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
