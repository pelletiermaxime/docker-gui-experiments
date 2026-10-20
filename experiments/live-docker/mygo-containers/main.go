package main

import (
	"context"
	"crypto/sha256"
	"fmt"
	"log"
	"sort"
	"strings"
	"time"

	"github.com/egoist/mygo"
	"github.com/egoist/mygo/ui"
	"github.com/moby/moby/client"
)

const maxContainers = 20_000

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

// All view state belongs to the UI thread; only the Docker API read runs away from it.
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
	{Title: "Name", Width: 250, MinWidth: 100},
	{Title: "Image", MinWidth: 150},
	{Title: "State", Width: 110},
	{Title: "Status", Width: 230},
}

func (s *app) view(c *ui.Context) {
	c.SetTheme(s.theme)
	t := c.Theme()
	ui.Column(c).Fill().Padding(24).Gap(16).Children(func() {
		ui.Row(c).AlignItems(ui.Center).Gap(12).Children(func() {
			ui.Text(c, "Containers").FontSize(26).Bold().Grow(1)
			ui.Text(c, "Go · MyGo · live Moby API").TextColor(t.TextMuted)
		})
		ui.Row(c).Gap(12).Children(func() {
			oldQuery := s.query
			ui.TextInput(c.Key("search"), &s.query).Placeholder("Search name, image or state…").Grow(1)
			if oldQuery != s.query {
				s.filter()
			}
			if ui.Button(c.Key("refresh"), "Refresh").Disabled(s.busy).Clicked() {
				s.refresh()
			}
		})
		status := fmt.Sprintf("%d / %d containers · all states", len(s.filtered), len(s.rows))
		if s.busy {
			status = "Loading…"
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
			ui.Text(c, "No matching containers.").TextColor(t.TextMuted)
		}
	})
}

func loadContainers() ([]container, error) {
	started := time.Now()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	cli, err := client.New(client.FromEnv)
	if err != nil {
		return nil, err
	}
	defer cli.Close()
	result, err := cli.ContainerList(ctx, client.ContainerListOptions{All: true})
	if err != nil {
		return nil, fmt.Errorf("Docker API: %w", err)
	}
	if len(result.Items) > maxContainers {
		return nil, fmt.Errorf("Docker returned more than %d containers", maxContainers)
	}
	rows := make([]container, 0, len(result.Items))
	ids := make([]string, 0, len(result.Items))
	for _, item := range result.Items {
		names := make([]string, len(item.Names))
		for i, name := range item.Names {
			names[i] = strings.TrimPrefix(name, "/")
		}
		rows = append(rows, container{
			ID: item.ID, Names: strings.Join(names, ", "), Image: item.Image,
			State: string(item.State), Status: item.Status,
		})
		ids = append(ids, item.ID)
	}
	sort.Strings(ids)
	log.Printf("source=moby-api containers=%d ids_sha256=%x elapsed_ms=%d", len(rows), sha256.Sum256([]byte(strings.Join(ids, "\n"))), time.Since(started).Milliseconds())
	return rows, nil
}

func main() {
	s := &app{theme: ui.DarkTheme()}
	mygo.App.WhenReady(func() {
		mygo.Theme.SetSource(mygo.ThemeDark)
		s.window = mygo.NewWindow(mygo.WindowOptions{
			Title: "FerryDock · MyGo · live Docker", Width: 1000, Height: 680, Content: ui.View(s.view),
		})
		s.refresh()
	})
	if err := mygo.App.Run(); err != nil {
		log.Fatal(err)
	}
}
