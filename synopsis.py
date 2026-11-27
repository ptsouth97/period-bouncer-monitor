import os
import markdown


def create_target_page(
    target
):

    filename = (
        target
        .replace(" ", "_")
    )

    synopsis_file = (
        f"synopses/{filename}.md"
    )

    output_file = (
        f"dashboard/targets/{filename}.html"
    )

    if os.path.exists(
        synopsis_file
    ):

        with open(
            synopsis_file,
            "r",
            encoding="utf-8"
        ) as f:

            md_text = (
                f.read()
            )

        body_html = (
            markdown.markdown(
                md_text,
                extensions=[
                    "tables"
                ]
            )
        )

    else:

        body_html = """
        <p>
        Synopsis not yet available.
        </p>
        """

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            f"""
            <html>

            <head>

            <title>
            {target}
            </title>

            <style>

            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                max-width: 900px;
            }}

            table {{
                border-collapse: collapse;
            }}

            td, th {{
                border: 1px solid #ccc;
                padding: 8px;
            }}

            </style>

            </head>

            <body>

            <p>
            <a href="../dashboard.html">
            &larr; Back to Dashboard
            </a>
            </p>

            {body_html}

            </body>

            </html>
            """
        )

