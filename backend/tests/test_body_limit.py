import unittest

from starlette.responses import JSONResponse

from body_limit import RequestBodyLimitMiddleware


class BodyLimitTests(unittest.IsolatedAsyncioTestCase):
    async def run_request(self, chunks):
        sent = []
        received_bodies = []

        messages = [
            {
                "type": "http.request",
                "body": chunk,
                "more_body": index < len(chunks) - 1,
            }
            for index, chunk in enumerate(chunks)
        ]

        async def receive():
            if messages:
                return messages.pop(0)

            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        async def app(scope, receive, send):
            message = await receive()
            received_bodies.append(message["body"])
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        middleware = RequestBodyLimitMiddleware(app, max_bytes=8)

        await middleware(
            {
                "type": "http",
                "method": "POST",
                "path": "/test",
                "headers": [(b"content-length", b"1")],
            },
            receive,
            send,
        )

        status = next(
            message["status"]
            for message in sent
            if message["type"] == "http.response.start"
        )

        return status, received_bodies

    async def test_exact_limit_is_accepted(self):
        status, bodies = await self.run_request([b"1234", b"5678"])

        self.assertEqual(status, 200)
        self.assertEqual(bodies, [b"12345678"])

    async def test_over_limit_never_reaches_app(self):
        status, bodies = await self.run_request([b"1234", b"56789"])

        self.assertEqual(status, 413)
        self.assertEqual(bodies, [])