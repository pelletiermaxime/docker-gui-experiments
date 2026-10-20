package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/egoist/mygo"
	"github.com/egoist/mygo/ui"
)

const maxSnapshot = 4 << 20

type container struct {
	ID, Names, Image, State, Status string
}

type app struct {
	window           *mygo.Window
	rows, filtered   []container
	query, errorText string
	busy             bool
	list             ui.ListState
	theme            *ui.Theme
}

// All view state belongs to the UI thread; only the Docker/file read runs away from it.
func (s *app) refresh() {
	if s.busy {
		return
	}
	s.busy, s.errorText = true, ""
	go func() {
		rows, err := loadContainers()
		mygo.RunOnMain(func() {
			s.busy = false
			if err != nil {
				s.errorText = err.Error()
			} else {
				s.rows = rows
				s.filter()
			}
			s.window.Invalidate()
		})
	}()
}

func (s *app) filter() {
	q := strings.ToLower(strings.TrimSpace(s.query))
	s.filtered = s.filtered[:0]
	for _, row := range s.rows {
		if q == "" || strings.Contains(strings.ToLower(row.Names+" "+row.Image+" "+row.State), q) {
			s.filtered = append(s.filtered, row)
		}
	}
}

var columns = []ui.TableColumn{
	{Title: "Nom", Width: 250, MinWidth: 100},
	{Title: "Image", MinWidth: 150},
	{Title: "État", Width: 110},
	{Title: "Statut", Width: 230},
}

func (s *app) view(c *ui.Context) {
	c.SetTheme(s.theme)
	t := c.Theme()
	ui.Column(c).Fill().Padding(24).Gap(16).Children(func() {
		ui.Row(c).AlignItems(ui.Center).Gap(12).Children(func() {
			ui.Text(c, "Containers").FontSize(26).Bold().Grow(1)
			ui.Text(c, "Go · MyGo native UI").TextColor(t.TextMuted)
		})
		ui.Row(c).Gap(12).Children(func() {
			oldQuery := s.query
			ui.TextInput(c.Key("search"), &s.query).Placeholder("Rechercher nom, image ou état…").Grow(1)
			if oldQuery != s.query {
				s.filter()
			}
			if ui.Button(c.Key("refresh"), "Refresh").Disabled(s.busy).Clicked() {
				s.refresh()
			}
		})
		status := fmt.Sprintf("%d / %d containers · tous les états", len(s.filtered), len(s.rows))
		if s.busy {
			status = "Chargement…"
		}
		ui.Text(c, status).TextColor(t.TextMuted)
		if s.errorText != "" {
			ui.Text(c, s.errorText).TextColor(t.Danger)
		}
		ui.Table(c.Key("containers"), &s.list, columns, len(s.filtered), func(row, col int) {
			r := &s.filtered[row]
			values := [4]string{r.Names, r.Image, r.State, r.Status}
			text := ui.Text(c, values[col]).SingleLine()
			if col == 2 && r.State == "running" {
				text.TextColor(t.Success)
			}
		}).Grow(1)
		if !s.busy && s.errorText == "" && len(s.filtered) == 0 {
			ui.Text(c, "Aucun container correspondant.").TextColor(t.TextMuted)
		}
	})
}

// Keep command output bounded even when the daemon writes unexpected amounts.
type boundedOutput struct {
	bytes.Buffer
	limit    int
	overflow bool
}

func (b *boundedOutput) Write(p []byte) (int, error) {
	n := len(p)
	if len(p) > b.limit-b.Len() {
		b.overflow = true
		p = p[:b.limit-b.Len()]
	}
	_, _ = b.Buffer.Write(p)
	return n, nil
}

func loadContainers() ([]container, error) {
	var data []byte
	if path := os.Getenv("CONTAINER_SNAPSHOT"); path != "" {
		f, err := os.Open(path)
		if err != nil {
			return nil, err
		}
		defer f.Close()
		data, err = io.ReadAll(io.LimitReader(f, maxSnapshot+1))
		if err != nil {
			return nil, err
		}
		if len(data) > maxSnapshot {
			return nil, fmt.Errorf("snapshot supérieur à 4 Mio")
		}
	} else {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		cmd := exec.CommandContext(ctx, "docker", "ps", "--all", "--no-trunc", "--format", "{{json .}}")
		out, stderr := &boundedOutput{limit: maxSnapshot}, &boundedOutput{limit: 4096}
		cmd.Stdout, cmd.Stderr = out, stderr
		if err := cmd.Run(); err != nil {
			return nil, fmt.Errorf("Docker : %w · %s", err, strings.TrimSpace(stderr.String()))
		}
		if out.overflow {
			return nil, fmt.Errorf("sortie Docker supérieure à 4 Mio")
		}
		data = out.Bytes()
	}
	rows := make([]container, 0)
	scanner := bufio.NewScanner(bytes.NewReader(data))
	scanner.Buffer(make([]byte, 4096), maxSnapshot)
	for scanner.Scan() {
		if len(bytes.TrimSpace(scanner.Bytes())) == 0 {
			continue
		}
		var row container
		if err := json.Unmarshal(scanner.Bytes(), &row); err != nil {
			return nil, fmt.Errorf("JSON du container %d : %w", len(rows)+1, err)
		}
		rows = append(rows, row)
	}
	return rows, scanner.Err()
}

func main() {
	s := &app{theme: ui.DarkTheme()}
	mygo.App.WhenReady(func() {
		mygo.Theme.SetSource(mygo.ThemeDark)
		s.window = mygo.NewWindow(mygo.WindowOptions{
			Title: "FerryDock · MyGo", Width: 1000, Height: 680, Content: ui.View(s.view),
		})
		s.refresh()
	})
	if err := mygo.App.Run(); err != nil {
		log.Fatal(err)
	}
}
