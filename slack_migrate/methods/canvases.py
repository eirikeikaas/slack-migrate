import click
import csv as csv_lib
import json
import os
import sys
from tabulate import tabulate
from ..api import (fetch_canvases, download_canvas_content, create_canvas)
from ..html_to_markdown import html_to_markdown

CANVAS_DIR = os.path.join("data", "canvases")
MANIFEST_PATH = os.path.join(CANVAS_DIR, "manifest.json")


def _load_manifest():
    try:
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@click.group('canvases')
def canvases_group():
    """Commands related to Slack canvases."""
    pass


@canvases_group.command('fetch')
@click.option('--refresh', is_flag=True, help='Force refresh of cached canvas data')
@click.option('--csv', is_flag=True, help='Export canvases to CSV file')
def fetch_canvases_cmd(refresh, csv):
    """Fetch canvases from Slack workspace."""
    canvases = fetch_canvases(refresh=refresh)

    rows = [{
        'id': c['id'],
        'title': c.get('title') or c.get('name', ''),
        'channel_id': c.get('channel_id') or '',
        'created': c.get('created', ''),
    } for c in canvases]

    if csv:
        os.makedirs('data', exist_ok=True)
        with open('data/canvases.csv', 'w', newline='') as csvfile:
            writer = csv_lib.DictWriter(
                csvfile, fieldnames=['id', 'title', 'channel_id', 'created'])
            writer.writeheader()
            writer.writerows(rows)
        click.echo("Canvases exported to data/canvases.csv")
    else:
        click.echo(tabulate(
            [[r['id'], r['title'], r['channel_id']] for r in rows],
            tablefmt="plain"))
    click.echo(f"total {len(rows)}")


@canvases_group.command('download')
@click.option('--refresh', is_flag=True, help='Force refresh of cached canvas data')
def download_canvases_cmd(refresh):
    """Download canvas content to data/canvases/."""
    canvases = fetch_canvases(refresh=refresh)
    os.makedirs(CANVAS_DIR, exist_ok=True)

    manifest = {}
    failed = []

    with click.progressbar(canvases, label='Downloading') as items:
        for canvas in items:
            try:
                html = download_canvas_content(canvas['id'])
                with open(os.path.join(CANVAS_DIR, f"{canvas['id']}.html"),
                          'w', encoding='utf-8') as f:
                    f.write(html)
                manifest[canvas['id']] = {
                    'title': canvas.get('title') or canvas.get('name', ''),
                    'channel_id': canvas.get('channel_id'),
                }
            except Exception as e:
                failed.append((canvas['id'], str(e)))

    with open(MANIFEST_PATH, 'w') as f:
        json.dump(manifest, f, indent=2)

    click.echo("\nCanvas download complete:")
    click.echo(f"  - Total: {len(canvases)}")
    click.echo(f"  - Downloaded: {len(manifest)}")
    click.echo(f"  - Failed: {len(failed)}")
    for canvas_id, error in failed:
        click.echo(f"    {canvas_id}: {error}")


@canvases_group.command('recreate')
@click.argument('canvas_ids', nargs=-1)
@click.option('--channel', 'channel_id', help='Create as the channel canvas of this channel (single canvas only)')
@click.option('--dry-run', is_flag=True, help='Show what would be created without creating it')
def recreate_canvases_cmd(canvas_ids, channel_id, dry_run):
    """Re-create downloaded canvases in Slack.

    CANVAS_IDS are IDs previously saved by `canvases download`; if omitted,
    IDs are read from stdin (one per line).
    """
    if not canvas_ids:
        if sys.stdin.isatty():
            raise click.UsageError("Provide canvas IDs or pipe them via stdin.")
        canvas_ids = [line.strip() for line in sys.stdin if line.strip()]

    if channel_id and len(canvas_ids) != 1:
        raise click.UsageError("--channel requires exactly one canvas ID.")

    manifest = _load_manifest()
    created = 0
    failed = []

    for canvas_id in canvas_ids:
        try:
            path = os.path.join(CANVAS_DIR, f"{canvas_id}.html")
            if not os.path.exists(path):
                raise Exception("not downloaded; run `canvases download` first")
            title = manifest.get(canvas_id, {}).get('title') or canvas_id

            if dry_run:
                target = f"channel {channel_id}" if channel_id else "standalone canvas"
                click.echo(f"[dry-run] Would create '{title}' as {target}")
                continue

            with open(path, encoding='utf-8') as f:
                markdown = html_to_markdown(f.read())
            new_id = create_canvas(title, markdown, channel_id=channel_id)
            click.echo(f"{canvas_id} -> {new_id}")
            created += 1
        except Exception as e:
            failed.append((canvas_id, str(e)))

    if not dry_run:
        click.echo(f"Created {created} canvas(es), {len(failed)} failed")
    for canvas_id, error in failed:
        click.echo(f"  {canvas_id}: {error}")
