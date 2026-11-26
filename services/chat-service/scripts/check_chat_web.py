#!/usr/bin/env python3
"""Optional browser checks. Requires Python Playwright and its Chromium browser.

Run chat-web separately, then: python3 scripts/check_chat_web.py
Gateway is replaced with an in-browser WebSocket stub; this is not a live
integration test of Gateway. No test hooks are added to production code.
"""

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


MOCK_WEBSOCKET = """
window.mockSockets = [];
class MockWebSocket {
  static OPEN = 1;
  constructor(url) { this.url = url; this.readyState = 0; this.sent = []; mockSockets.push(this); }
  send(text) { this.sent.push(JSON.parse(text)); }
  close() { this.readyState = 3; if (this.onclose) this.onclose({code: 1000}); }
  open() { this.readyState = 1; this.onopen(); }
  receive(data) { this.onmessage({data: JSON.stringify(data)}); }
}
window.WebSocket = MockWebSocket;
"""


def run_checks(browser, url, screenshot_dir=None):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(url)
        chat = page.locator("plotina-chat")
        expect(chat.locator(".message")).to_have_count(5)
        bounds = chat.bounding_box()
        assert bounds["width"] <= 420 and bounds["height"] == 570
        expect(chat.get_by_text("Деморежим", exact=True).first).to_be_visible()
        if screenshot_dir:
            Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(screenshot_dir) / "chat-desktop.png"), full_page=True)
        message = chat.get_by_role("textbox", name="Сообщение", exact=True)
        message.fill("Моё сообщение")
        message.press("Enter")
        expect(chat.locator(".message")).to_have_count(6)
        expect(chat.locator(".message").last.locator(".author")).to_have_text("Вы")
        expect(chat.locator(".message").last.locator("p")).to_have_text("Моё сообщение")
        message.fill("Первая строка")
        message.press("Shift+Enter")
        message.type("Вторая строка")
        message.press("Enter")
        expect(chat.locator(".message").last.locator("p")).to_have_text("Первая строка\nВторая строка")
        message.fill('<img src=x onerror="window.xss=true">')
        message.press("Enter")
        assert chat.locator(".messages img").count() == 0
        assert page.evaluate("window.xss") is None
        chat.get_by_role("button", name="Стикеры — скоро").click()
        expect(chat.locator(".notice")).to_contain_text("Стикеры скоро появятся")
        chat.get_by_role("button", name="Скрыть уведомление").click()

        page.evaluate("""() => {
          const widget = document.querySelector('plotina-chat');
          for (let i = 0; i < 25; i++) widget.appendMessage({message_id: 'test-' + i,
            participant_id: 'demo-anna', messageSeq: 50 + i, text: 'Сообщение ' + i, created_at: new Date().toISOString()});
        }""")
        expect(chat.locator(".message")).to_have_count(33)
        page.evaluate("""() => {
          const feed = document.querySelector('plotina-chat').shadowRoot.querySelector('.feed');
          feed.scrollTop = 0;
          feed.dispatchEvent(new Event('scroll'));
          document.querySelector('plotina-chat').appendMessage({message_id: 'new', participant_id: 'demo-dima',
            messageSeq: 90, text: 'Новое внизу', created_at: new Date().toISOString()});
        }""")
        expect(chat.locator(".new-messages")).to_be_visible()
        assert chat.locator(".feed").evaluate("feed => feed.scrollTop") == 0
        chat.locator(".new-messages").click()
        expect(chat.locator(".new-messages")).to_be_hidden()

        page.set_viewport_size({"width": 360, "height": 800})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert chat.bounding_box()["width"] <= 360
        if screenshot_dir:
            page.screenshot(path=str(Path(screenshot_dir) / "chat-mobile.png"), full_page=True)

        # Validate real component behaviour against the agreed Gateway messages.
        page.add_init_script(MOCK_WEBSOCKET)
        page.reload()
        expect(chat.locator(".message")).to_have_count(5)
        chat.get_by_role("button", name="Настройки подключения").click()
        chat.get_by_label("Токен участника").fill("private-test-token")
        chat.get_by_role("button", name="Подключиться", exact=True).click()
        page.evaluate("mockSockets[0].open()")
        assert page.evaluate("mockSockets[0].sent[0].type") == "getState"
        expect(message).to_be_disabled()
        page.evaluate("""() => mockSockets[0].receive({type: 'sendState', initialMessageSeq: 10,
          state: {participants: [{participant_id: 'alice', display_name: 'Алиса', connected: true}]}})""")
        expect(message).to_be_enabled()
        expect(chat.locator(".message")).to_have_count(0)
        page.evaluate("""() => {
          window.incoming = (seq, text='Текст ' + seq, id='alice') => ({message_id: 'm-' + seq,
            participant_id: id, messageSeq: seq, text, created_at: new Date().toISOString()});
          mockSockets[0].receive({type: 'sendMessage', message: incoming(12)});
        }""")
        expect(chat.locator(".message")).to_have_count(0)
        expect(chat.locator(".notice")).to_contain_text("Ожидаем сообщение №11")
        page.evaluate("mockSockets[0].receive({type: 'sendMessage', message: incoming(11)})")
        expect(chat.locator(".message")).to_have_count(2)
        assert chat.locator(".message").evaluate_all("rows => rows.map(row => row.dataset.seq)") == ["11", "12"]
        expect(chat.locator(".notice")).to_be_hidden()
        expect(chat.locator(".message").first.locator(".author")).to_have_text("Алиса")
        page.evaluate("mockSockets[0].receive({type: 'sendMessage', message: incoming(11)})")
        expect(chat.locator(".message")).to_have_count(2)
        message.fill("Отправка через Gateway")
        message.press("Enter")
        assert page.evaluate("mockSockets[0].sent.at(-1).type") == "sendMessage"
        expect(chat.locator(".pending")).to_be_visible()
        expect(chat.get_by_role("button", name="Отправить сообщение")).to_be_disabled()
        page.evaluate("""() => {
          const sent = mockSockets[0].sent.at(-1);
          mockSockets[0].receive({type: 'commandConfirm', commandId: sent.commandId, duplicate: false,
            message: incoming(13, sent.payload.text, 'self-id')});
        }""")
        expect(chat.locator(".message")).to_have_count(3)
        expect(chat.locator(".message").last.locator(".author")).to_have_text("Вы")
        expect(chat.locator(".pending")).to_be_hidden()
        page.evaluate("mockSockets[0].receive({type: 'pig', pigId: 'heartbeat-1'})")
        assert page.evaluate("mockSockets[0].sent.at(-1)") == {"type": "pong", "pigId": "heartbeat-1"}
        # Do not guess a missing display_name: an unknown author is shown by ID.
        page.evaluate("mockSockets[0].receive({type: 'sendMessage', message: incoming(14, 'Новый участник', 'participant-unknown')})")
        expect(chat.locator(".message").last.locator(".author")).to_have_text("participant-unknown")
        # A reconnect accepts a new baseline and must not replay offline history.
        message.fill("Повтор после обрыва")
        message.press("Enter")
        old_command_id = page.evaluate("mockSockets[0].sent.at(-1).commandId")
        page.evaluate("mockSockets[0].close()")
        expect(message).to_be_disabled()
        page.wait_for_function("mockSockets.length === 2")
        page.evaluate("""() => {
          mockSockets[1].open();
          mockSockets[1].receive({type: 'sendState', initialMessageSeq: 20, state: {participants: []}});
        }""")
        assert page.evaluate("mockSockets[1].sent.at(-1).commandId") == old_command_id
        page.evaluate("""() => {
          const sent = mockSockets[1].sent.at(-1);
          mockSockets[1].receive({type: 'commandConfirm', commandId: sent.commandId, duplicate: true,
            message: incoming(16, sent.payload.text, 'self-id')});
          mockSockets[1].receive({type: 'sendMessage', message: incoming(19)});
          mockSockets[1].receive({type: 'sendMessage', message: incoming(21)});
        }""")
        expect(chat.locator(".message")).to_have_count(5)
        assert chat.locator(".message").last.get_attribute("data-seq") == "21"
        expect(chat.locator(".pending")).to_be_hidden()
        assert page.evaluate("localStorage.length === 0 && sessionStorage.length === 0")
        assert "private-test-token" not in page.content()
        assert not errors, errors
        print("PASS: desktop/mobile UI, input, authors, sticker placeholder, safe text, scroll/unread, Gateway ordering/deduplication/ack, reconnect and heartbeat")
    finally:
        page.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8099")
    parser.add_argument("--screenshots", help="directory for desktop and mobile screenshots")
    parser.add_argument("--browser-executable", help="optional existing Chromium executable")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        options = {"headless": True}
        if args.browser_executable:
            options["executable_path"] = args.browser_executable
        browser = playwright.chromium.launch(**options)
        try:
            run_checks(browser, args.url, args.screenshots)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
