"""ORM models used by the scraping plug-in."""
from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.database import Base


class ScrapeJob(Base):
    """Represents a single scraping execution."""

    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(255))
    chart_title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_payload: Mapped[str | None] = mapped_column(Text)

    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="job", cascade="all, delete-orphan"
    )
    datasets: Mapped[List["ChartDataset"]] = relationship(
        "ChartDataset", back_populates="job", cascade="all, delete-orphan"
    )
    images: Mapped[List["ScrapedImage"]] = relationship(
        "ScrapedImage", back_populates="job", cascade="all, delete-orphan"
    )


class Product(Base):
    """Stores product cards extracted from the target page."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("scrape_jobs.id", ondelete="CASCADE"))
    name: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(8))
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)

    job: Mapped[ScrapeJob] = relationship("ScrapeJob", back_populates="products")


class ChartDataset(Base):
    """Stores normalised chart datasets."""

    __tablename__ = "chart_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("scrape_jobs.id", ondelete="CASCADE"))
    label: Mapped[str | None] = mapped_column(String(255))
    labels_json: Mapped[str] = mapped_column(Text)
    values_json: Mapped[str] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(32))

    job: Mapped[ScrapeJob] = relationship("ScrapeJob", back_populates="datasets")


class ScrapedImage(Base):
    """References chart or product imagery discovered on the page."""

    __tablename__ = "scraped_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("scrape_jobs.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(String(64))

    job: Mapped[ScrapeJob] = relationship("ScrapeJob", back_populates="images")


__all__ = [
    "ScrapeJob",
    "Product",
    "ChartDataset",
    "ScrapedImage",
]
