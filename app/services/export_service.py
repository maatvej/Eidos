# filename: app/services/export_service.py
"""Multi-format export generator (TXT, SRT, VTT, JSON, DOCX, PDF)."""

import io

from app.core.profiler import profile_sync
from app.domain.entities import TranscriptionResult
from app.domain.exceptions import ExportGenerationError


class ExportService:
    """Generates formatted document outputs from transcript models."""

    @staticmethod
    def _format_timestamp_srt(seconds: float) -> str:
        millis = int((seconds - int(seconds)) * 1000)
        seconds_int = int(seconds)
        hours = seconds_int // 3600
        minutes = (seconds_int % 3600) // 60
        secs = seconds_int % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def _format_timestamp_vtt(seconds: float) -> str:
        return ExportService._format_timestamp_srt(seconds).replace(",", ".")

    @profile_sync(name="export_to_txt", subfolder="exports")
    def to_txt(self, result: TranscriptionResult) -> str:
        """Exports transcription result and executive analysis into plain text representation.

        Args:
            result: Transcription result domain entity.

        Returns:
            Formatted plain text string.

        Example:
            >>> txt = service.to_txt(result)
        """
        lines: list[str] = []
        if result.analysis:
            lines.append("=== MEETING SUMMARY / ВЫЖИМКА ВСТРЕЧИ ===")
            lines.append(result.analysis.executive_summary)
            lines.append("\n=== KEY DECISIONS / КЛЮЧЕВЫЕ РЕШЕНИЯ ===")
            lines.extend(f"• {dec}" for dec in result.analysis.key_decisions)
            lines.append("\n=== ACTION ITEMS / ЗАДАЧИ ===")
            lines.extend(
                f"[{item.priority}] {item.task} (Owner: {item.owner or 'Unassigned'})"
                for item in result.analysis.action_items
            )
            lines.append("\n" + "=" * 40 + "\n")

        lines.append("=== FULL TRANSCRIPT / ПОЛНАЯ СТЕНОГРАММА ===")
        lines.extend(
            f"[{self._format_timestamp_srt(utt.start)} - {self._format_timestamp_srt(utt.end)}] {utt.speaker}: {utt.text}"
            for utt in result.utterances
        )

        return "\n".join(lines)

    @profile_sync(name="export_to_srt", subfolder="exports")
    def to_srt(self, result: TranscriptionResult) -> str:
        """Exports transcription result into standard SubRip Subtitle (SRT) format.

        Args:
            result: Transcription result domain entity.

        Returns:
            SRT formatted string.

        Example:
            >>> srt = service.to_srt(result)
        """
        lines: list[str] = []
        count = 1
        for utt in result.utterances:
            start_str = self._format_timestamp_srt(utt.start)
            end_str = self._format_timestamp_srt(utt.end)
            lines.append(f"{count}\n{start_str} --> {end_str}\n[{utt.speaker}]: {utt.text}\n")
            count += 1
        return "\n".join(lines)

    @profile_sync(name="export_to_vtt", subfolder="exports")
    def to_vtt(self, result: TranscriptionResult) -> str:
        """Exports transcription result into Web Video Text Tracks (WebVTT) format.

        Args:
            result: Transcription result domain entity.

        Returns:
            WebVTT formatted string.

        Example:
            >>> vtt = service.to_vtt(result)
        """
        lines: list[str] = ["WEBVTT\n"]
        for utt in result.utterances:
            start_str = self._format_timestamp_vtt(utt.start)
            end_str = self._format_timestamp_vtt(utt.end)
            lines.append(f"{start_str} --> {end_str}\n<v {utt.speaker}>{utt.text}\n")
        return "\n".join(lines)

    @profile_sync(name="export_to_docx", subfolder="exports")
    def to_docx(self, result: TranscriptionResult) -> bytes:
        """Exports transcription result and summary into formatted Microsoft Word (DOCX) binary bytes.

        Args:
            result: Transcription result domain entity.

        Returns:
            DOCX document binary content bytes.

        Raises:
            ExportGenerationError: If DOCX generation encounters an error.

        Example:
            >>> docx_bytes = service.to_docx(result)
        """
        try:
            from docx import Document

            doc = Document()
            doc.add_heading("Transcription Report", level=0)

            if result.analysis:
                doc.add_heading("Executive Summary", level=1)
                doc.add_paragraph(result.analysis.executive_summary)

                doc.add_heading("Key Decisions", level=2)
                for dec in result.analysis.key_decisions:
                    doc.add_paragraph(f"• {dec}")

                doc.add_heading("Action Items", level=2)
                for item in result.analysis.action_items:
                    doc.add_paragraph(
                        f"[{item.priority}] {item.task} (Owner: {item.owner or 'Unassigned'})"
                    )

            doc.add_heading("Full Transcript", level=1)
            for utt in result.utterances:
                p = doc.add_paragraph()
                p.add_run(f"{utt.speaker} ({round(utt.start, 1)}s): ").bold = True
                p.add_run(utt.text)

            buffer = io.BytesIO()
            doc.save(buffer)
            return buffer.getvalue()
        except Exception as e:
            raise ExportGenerationError("DOCX", str(e))

    @profile_sync(name="export_to_pdf", subfolder="exports")
    def to_pdf(self, result: TranscriptionResult) -> bytes:
        """Exports transcription result and executive report into Adobe PDF binary bytes.

        Args:
            result: Transcription result domain entity.

        Returns:
            PDF document binary content bytes.

        Raises:
            ExportGenerationError: If PDF generation encounters an error.

        Example:
            >>> pdf_bytes = service.to_pdf(result)
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            title_style = styles["Heading1"]
            speaker_style = ParagraphStyle(
                "SpeakerStyle", parent=styles["Normal"], fontName="Helvetica-Bold"
            )
            text_style = styles["Normal"]

            story.append(Paragraph("Conversation Intelligence Report", title_style))
            story.append(Spacer(1, 12))

            if result.analysis:
                story.append(Paragraph("Executive Summary", styles["Heading2"]))
                story.append(Paragraph(result.analysis.executive_summary, text_style))
                story.append(Spacer(1, 10))

            story.append(Paragraph("Transcript", styles["Heading2"]))
            for utt in result.utterances:
                story.append(Paragraph(f"{utt.speaker} ({round(utt.start, 1)}s)", speaker_style))
                story.append(Paragraph(utt.text, text_style))
                story.append(Spacer(1, 6))

            doc.build(story)
            return buffer.getvalue()
        except Exception as e:
            raise ExportGenerationError("PDF", str(e))
