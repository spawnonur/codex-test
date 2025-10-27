from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

import requests
from flask import Flask, jsonify, render_template, request
from sqlalchemy import select

from data import scraper
from data.database import SessionLocal, init_db
from data.models import ChartDataset, Product, ScrapeJob, ScrapedImage

app = Flask(__name__)
init_db()


@contextmanager
def get_session() -> Generator:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def serialise_job(job: ScrapeJob) -> dict:
    return {
        "id": job.id,
        "url": job.url,
        "title": job.title,
        "chart_title": job.chart_title,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "datasets": [
            {
                "label": dataset.label,
                "labels": json.loads(dataset.labels_json),
                "values": json.loads(dataset.values_json),
                "color": dataset.color,
            }
            for dataset in job.datasets
        ],
        "products": [
            {
                "name": product.name,
                "price": product.price,
                "currency": product.currency,
                "description": product.description,
                "image_url": product.image_url,
            }
            for product in job.products
        ],
        "images": [
            {
                "url": image.url,
                "alt": image.alt_text,
                "context": image.context,
            }
            for image in job.images
        ],
    }


def job_summary(job: ScrapeJob) -> dict:
    return {
        "id": job.id,
        "url": job.url,
        "title": job.title,
        "chart_title": job.chart_title,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "product_count": len(job.products),
        "dataset_count": len(job.datasets),
    }


@app.get("/")
def index() -> str:
    with get_session() as session:
        jobs = session.scalars(select(ScrapeJob).order_by(ScrapeJob.created_at.desc())).all()
        jobs_payload = [job_summary(job) for job in jobs]
    return render_template("index.html", jobs_json=json.dumps(jobs_payload, ensure_ascii=False))


@app.post("/scrape")
def trigger_scrape():
    use_sample = request.form.get("use_sample") == "1"
    url = request.form.get("url", "").strip()

    if use_sample:
        html_override = scraper.load_sample_html()
        url = "örnek://yerel"
    else:
        html_override = None
        if not url:
            return jsonify({"error": "Lütfen geçerli bir URL girin."}), 400

    try:
        result = scraper.scrape(url=url, html_override=html_override)
    except requests.RequestException as exc:
        return jsonify({"error": f"İstek başarısız: {exc}"}), 502
    except scraper.ScraperError as exc:
        return jsonify({"error": str(exc)}), 400

    with get_session() as session:
        job = ScrapeJob(
            url=result.url,
            title=result.title,
            chart_title=result.chart_title,
            raw_payload=result.raw_payload,
            created_at=datetime.utcnow(),
        )
        session.add(job)
        session.flush()

        for product in result.products:
            session.add(
                Product(
                    job_id=job.id,
                    name=product.name,
                    price=product.price,
                    currency=product.currency,
                    description=product.description,
                    image_url=product.image_url,
                )
            )

        for dataset in result.datasets:
            session.add(
                ChartDataset(
                    job_id=job.id,
                    label=dataset.label,
                    labels_json=json.dumps(dataset.labels, ensure_ascii=False),
                    values_json=json.dumps(dataset.values, ensure_ascii=False),
                    color=dataset.color,
                )
            )

        for src, alt, context in result.images:
            session.add(
                ScrapedImage(
                    job_id=job.id,
                    url=src,
                    alt_text=alt,
                    context=context,
                )
            )

        session.flush()
        job_payload = serialise_job(job)

    return jsonify({"job": job_payload})


@app.get("/api/jobs")
def list_jobs():
    with get_session() as session:
        jobs = session.scalars(select(ScrapeJob).order_by(ScrapeJob.created_at.desc())).all()
        payload = [job_summary(job) for job in jobs]
    return jsonify(payload)


@app.get("/api/jobs/<int:job_id>")
def job_detail(job_id: int):
    with get_session() as session:
        job = session.get(ScrapeJob, job_id)
        if not job:
            return jsonify({"error": "Kayıt bulunamadı."}), 404
        payload = serialise_job(job)
    return jsonify(payload)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
