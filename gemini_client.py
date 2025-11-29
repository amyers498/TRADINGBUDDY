"""Gemini API client wrapper."""
from __future__ import annotations

import logging
import textwrap
from datetime import date
from typing import Iterable, List

import pandas as pd
import requests

import config

LOGGER = logging.getLogger(__name__)


class GeminiClient:
    """Encapsulates prompt construction and API calls to Gemini."""

    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: int = 60,
        model_name: str | None = None,
    ) -> None:
        self.api_key = api_key or config.GEMINI_API_KEY
        self.timeout = timeout
        self.model_name = model_name or config.GEMINI_MODEL_NAME

    def generate_daily_report(
        self, trade_date: date, trades_df: pd.DataFrame, trade_summary: str
    ) -> str:
        """Generate a markdown report for a single day of trades."""
        sample = self._dataframe_sample(trades_df)
        prompt = textwrap.dedent(
            f"""
            You are an elite trading coach. Review the following trade log for {trade_date:%Y-%m-%d}.
            Produce a tight, stylish markdown brief (<220 words) with these sections:
            ## Pulse Check - 2 bullets on win/loss + risk-reward
            ## Mistakes to Fix - 2 bullets
            ## Focus & Mindset - 2 bullets
            ## Next Session - EXACTLY three numbered action items

            Keep sentences crisp and punchy. When judging PnL, account for any fees/commissions present so net results reflect costs.

            Trade summary (all rows):
            {trade_summary}

            Trade sample (first rows):
            {sample}
            """
        ).strip()
        return self._call_gemini(prompt)

    def generate_weekly_report(
        self,
        start_date: date,
        end_date: date,
        daily_reports_texts: Iterable[str],
    ) -> str:
        """Summarize a full week of daily reports."""
        reports_blob = "\n\n".join(daily_reports_texts)
        prompt = textwrap.dedent(
            f"""
            Summarize the following daily trading reports for {start_date:%Y-%m-%d} to {end_date:%Y-%m-%d}.
            Keep it under 180 words with markdown sections:
            ## Weekly Pulse (wins/losses + momentum) — 2 bullets
            ## Recurring Mistakes — 2 bullets
            ## Bright Spots — 2 bullets
            ## Focus for Next Week — 3 bullets

            Daily reports:
            {reports_blob}
            """
        ).strip()
        return self._call_gemini(prompt)

    def generate_monthly_report(
        self,
        month_start: date,
        month_end: date,
        weekly_reports_texts: Iterable[str],
    ) -> str:
        """Build a monthly markdown summary from weekly reports."""
        reports_blob = "\n\n".join(weekly_reports_texts)
        prompt = textwrap.dedent(
            f"""
            Create a high-level trading review for {month_start:%B %Y} ({month_start:%Y-%m-%d} to {month_end:%Y-%m-%d}).
            Keep it under 220 words with markdown sections:
            ## Macro Pulse — 2 bullets
            ## Strategy Insights — 2 bullets
            ## Risk & Psychology — 2 bullets
            ## Goals for Next Month — 3 bullets

            Weekly reports:
            {reports_blob}
            """
        ).strip()
        return self._call_gemini(prompt)

    @staticmethod
    def _dataframe_sample(df: pd.DataFrame, limit: int = 20) -> str:
        """Return a markdown sample of the dataframe."""
        subset = df.head(limit)
        try:
            return subset.to_markdown(index=False)
        except Exception:
            return subset.to_string(index=False)

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini with the provided prompt and return the generated text."""
        params = {"key": self.api_key}
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ]
        }
        LOGGER.info(
            "Calling Gemini API (%d chars) using model %s",
            len(prompt),
            self.model_name,
        )
        url = f"{self.API_BASE}/{self.model_name}:generateContent"
        response = requests.post(
            url,
            params=params,
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        candidates: List[dict] = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini API returned no candidates")
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text")
        if not text:
            raise RuntimeError("Gemini API response missing text")
        return text.strip()


