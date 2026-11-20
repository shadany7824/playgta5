// Local mirror server: isolation headers, byte ranges, and engine batch I/O.
package main

import (
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"mime"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const (
	maxRequestBody = 1024 * 1024
	maxRuns        = 1000
	maxBatchBytes  = 64 * 1024 * 1024
)

// run is one [name, start, end] triple (end is inclusive).
type run struct {
	name       string
	start, end int64
}

func (r *run) UnmarshalJSON(b []byte) error {
	var parts []json.RawMessage
	if err := json.Unmarshal(b, &parts); err != nil {
		return err
	}
	if len(parts) != 3 {
		return errors.New("invalid run")
	}
	if err := json.Unmarshal(parts[0], &r.name); err != nil {
		return err
	}
	if err := json.Unmarshal(parts[1], &r.start); err != nil {
		return err
	}
	return json.Unmarshal(parts[2], &r.end)
}

type server struct {
	root     string
	dataRoot string // symlink-resolved
	files    http.Handler
}

func newServer(root string) (*server, error) {
	absRoot, err := filepath.Abs(root)
	if err != nil {
		return nil, err
	}
	dataRoot := filepath.Join(absRoot, "data")
	if resolved, err := filepath.EvalSymlinks(dataRoot); err == nil {
		dataRoot = resolved
	}
	return &server{
		root:     absRoot,
		dataRoot: dataRoot,
		// http.FileServer handles Range requests (206/416) natively.
		files: http.FileServer(http.Dir(absRoot)),
	}, nil
}

func (s *server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	h := w.Header()
	h.Set("Cross-Origin-Opener-Policy", "same-origin")
	h.Set("Cross-Origin-Embedder-Policy", "require-corp")
	h.Set("Cross-Origin-Resource-Policy", "same-origin")
	h.Set("Accept-Ranges", "bytes")

	if r.Method == http.MethodPost {
		if r.URL.Path != "/data/batch" {
			http.Error(w, "Not Found", http.StatusNotFound)
			return
		}
		s.handleBatch(w, r)
		return
	}
	s.files.ServeHTTP(w, r)
}

func (s *server) handleBatch(w http.ResponseWriter, r *http.Request) {
	if r.ContentLength > maxRequestBody {
		http.Error(w, "Request Entity Too Large", http.StatusRequestEntityTooLarge)
		return
	}
	raw, err := io.ReadAll(http.MaxBytesReader(w, r.Body, maxRequestBody))
	if err != nil {
		var mbe *http.MaxBytesError
		if errors.As(err, &mbe) {
			http.Error(w, "Request Entity Too Large", http.StatusRequestEntityTooLarge)
			return
		}
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	body, lengths, compressed, err := s.buildBatch(raw, r.URL.Query().Get("gz") == "1")
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	strs := make([]string, len(lengths))
	for i, n := range lengths {
		strs[i] = strconv.FormatInt(n, 10)
	}
	h := w.Header()
	h.Set("Content-Type", "application/octet-stream")
	h.Set("Content-Length", strconv.Itoa(len(body)))
	h.Set("X-Run-Lengths", strings.Join(strs, ","))
	if compressed {
		h.Set("Content-Encoding", "gzip")
	}
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(body)
}

func (s *server) buildBatch(raw []byte, gz bool) (body []byte, lengths []int64, compressed bool, err error) {
	var runs []run
	if err = json.Unmarshal(raw, &runs); err != nil {
		return nil, nil, false, errors.New("invalid batch")
	}
	if len(runs) > maxRuns {
		return nil, nil, false, errors.New("invalid batch")
	}

	type selection struct {
		path     string
		start, n int64
	}
	selected := make([]selection, 0, len(runs))
	var total int64
	for _, rn := range runs {
		if rn.start < 0 || rn.end < rn.start {
			return nil, nil, false, errors.New("invalid file/range")
		}
		file, rerr := filepath.EvalSymlinks(filepath.Join(s.dataRoot, filepath.FromSlash(rn.name)))
		if rerr != nil {
			return nil, nil, false, rerr
		}
		rel, rerr := filepath.Rel(s.dataRoot, file)
		if rerr != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || filepath.IsAbs(rel) {
			return nil, nil, false, errors.New("invalid file/range")
		}
		info, rerr := os.Stat(file)
		if rerr != nil {
			return nil, nil, false, rerr
		}
		if !info.Mode().IsRegular() {
			return nil, nil, false, errors.New("not a regular file")
		}
		n := min(rn.end+1, info.Size()) - rn.start
		if n < 0 {
			n = 0
		}
		selected = append(selected, selection{file, rn.start, n})
		lengths = append(lengths, n)
		total += n
		if total > maxBatchBytes {
			return nil, nil, false, errors.New("batch exceeds 64 MiB")
		}
	}

	var out bytes.Buffer
	for _, sel := range selected {
		if sel.n == 0 {
			continue
		}
		f, oerr := os.Open(sel.path)
		if oerr != nil {
			return nil, nil, false, oerr
		}
		_, cerr := io.Copy(&out, io.NewSectionReader(f, sel.start, sel.n))
		f.Close()
		if cerr != nil {
			return nil, nil, false, cerr
		}
	}

	if !gz {
		return out.Bytes(), lengths, false, nil
	}
	var zbuf bytes.Buffer
	zw, _ := gzip.NewWriterLevel(&zbuf, 1)
	if _, err = zw.Write(out.Bytes()); err != nil {
		return nil, nil, false, err
	}
	if err = zw.Close(); err != nil {
		return nil, nil, false, err
	}
	return zbuf.Bytes(), lengths, true, nil
}

func openBrowser(url string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	_ = cmd.Start()
}

func main() {
	port := flag.Int("port", 8000, "port to listen on")
	open := flag.Bool("open", false, "open the default browser after binding")
	root := flag.String("root", filepath.Join("mirror", "playgta5.com"), "directory to serve")
	flag.Parse()

	_ = mime.AddExtensionType(".wasm", "application/wasm")
	_ = mime.AddExtensionType(".js", "text/javascript")

	srv, err := newServer(*root)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", *port))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	address := fmt.Sprintf("http://localhost:%d/", ln.Addr().(*net.TCPAddr).Port)
	fmt.Printf("Local mirror: %s (Ctrl+C to stop)\n", address)
	if *open {
		openBrowser(address)
	}

	httpServer := &http.Server{Handler: srv}
	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
		<-sig
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		_ = httpServer.Shutdown(ctx)
	}()

	if err := httpServer.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
