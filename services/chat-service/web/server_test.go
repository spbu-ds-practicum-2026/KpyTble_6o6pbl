package web_test

import (
	"net/http/httptest"
	"strings"
	"testing"

	"plotina/chat-service/web"
)

func TestEmbeddedFrontend(t *testing.T) {
	for _, path := range []string{"/", "/preview.js", "/preview.css", "/chat-widget.js", "/chat-widget.css", "/chat-client.js"} {
		recorder := httptest.NewRecorder()
		web.Handler().ServeHTTP(recorder, httptest.NewRequest("GET", path, nil))
		if recorder.Code != 200 || recorder.Body.Len() == 0 {
			t.Fatalf("%s: status=%d", path, recorder.Code)
		}
		if recorder.Header().Get("X-Content-Type-Options") != "nosniff" {
			t.Fatalf("missing asset response headers for %s", path)
		}
		if path == "/" && !strings.Contains(recorder.Body.String(), "<plotina-chat>") {
			t.Fatal("chat widget is missing from preview")
		}
	}
	recorder := httptest.NewRecorder()
	web.Handler().ServeHTTP(recorder, httptest.NewRequest("GET", "/server.go", nil))
	if recorder.Code != 404 {
		t.Fatal("Go sources must not be exposed as frontend assets")
	}
}
