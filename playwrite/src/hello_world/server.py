"""Hello World CLI web server application."""

import click
from flask import Flask, request

app = Flask(__name__)

INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hello World</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; }
    h1 { color: #333; }
    input[type="text"] { padding: 8px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; }
    button { padding: 8px 16px; font-size: 16px; background: #007bff; color: white;
             border: none; border-radius: 4px; cursor: pointer; margin-left: 8px; }
    button:hover { background: #0056b3; }
  </style>
</head>
<body>
  <h1>Hello World!</h1>
  <form action="/greet" method="post">
    <label for="name">Enter your name:</label><br><br>
    <input type="text" id="name" name="name" placeholder="Your name" autofocus>
    <button type="submit">Submit</button>
  </form>
</body>
</html>
"""

GREET_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hello {name}!</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; }}
    h1 {{ color: #007bff; }}
    a {{ color: #007bff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>Hello, {name}!</h1>
  <p><a href="/">Go back</a></p>
</body>
</html>
"""


@app.route("/")
def index() -> str:
    """Render the Hello World index page with name input form."""
    return INDEX_HTML


@app.route("/greet", methods=["POST"])
def greet() -> str:
    """Render the greeting page with the submitted name."""
    name = request.form.get("name", "").strip() or "World"
    return GREET_HTML.format(name=name)


@click.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind to.")
@click.option("--port", default=5000, show_default=True, help="Port to listen on.")
@click.option("--debug", is_flag=True, default=False, help="Enable Flask debug mode.")
def main(host: str, port: int, debug: bool) -> None:
    """Start the Hello World web server."""
    click.echo(f"Starting Hello World server at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    main()
