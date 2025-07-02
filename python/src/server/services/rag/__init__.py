"""
RAG Services Package

This package contains services specific to Retrieval Augmented Generation (RAG)
that don't fit into other service categories. Currently includes web crawling operations.
"""

from .crawling_service import CrawlingService

__all__ = [
    "CrawlingService"
]