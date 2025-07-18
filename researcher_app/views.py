# researcher_app/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from .models import (
    UploadedPDF, ExtractedContent, BlogOutline, BlogDraft, ChatMessage, NormalizationRule
)
from .serializers import (
    UploadedPDFSerializer, ExtractedContentSerializer,
    BlogOutlineSerializer, BlogDraftSerializer,
    ChatMessageSerializer, NormalizationRuleSerializer
)
from .services import pdf_extractor, outline, writer, formatter
from io import BytesIO
import tempfile
import threading
from django.shortcuts import render


def parse_pdf_async(pdf_id, file_path):
    print(f"DEBUG: Background parsing for PDF {pdf_id}")
    try:
        print(f"DEBUG: Starting extraction for {file_path}")
        result = pdf_extractor.extract_pdf(file_path)

        print(
            f"DEBUG: Extraction result - text len={len(result['text'])}, "
            f"images={len(result['images'])}, tables={len(result['tables'])}"
        )

        pdf = UploadedPDF.objects.get(id=pdf_id)
        print(f"DEBUG: PDF object found - {pdf}")

        # ✅ Save extracted content
        ExtractedContent.objects.create(
            pdf=pdf,
            text=result['text'],
            images=result['images'],
            tables=result['tables']
        )
        print("✅ Saved extracted content to DB")

        print(f"✅ Background parsing completed for PDF {pdf_id}")

    except Exception as e:
        print(f"❌ Background parsing failed for PDF {pdf_id}: {e}")


class UploadPDFView(APIView):
    """
    API to upload a PDF and parse in background.
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        print("DEBUG: request.data =", request.data)
        print("DEBUG: request.FILES =", request.FILES)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {"error": "No file provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UploadedPDFSerializer(data=request.data)
        if serializer.is_valid():
            pdf = serializer.save()
            # Kick off background parse
            threading.Thread(
                target=parse_pdf_async,
                args=(pdf.id, pdf.file.path),
                daemon=True
            ).start()

            return Response({
                "id": pdf.id,
                "url": pdf.file.url,
                "parse_status": "pending"
            }, status=status.HTTP_201_CREATED)
        else:
            print("DEBUG: serializer errors =", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExtractPDFView(APIView):
    """
    GET:  return existing extracted content.
    POST: re-run extraction and update.
    """

    def get(self, request, pk, *args, **kwargs):
        try:
            content_obj = ExtractedContent.objects.get(pdf__pk=pk)
        except ExtractedContent.DoesNotExist:
            return Response(
                {"error": "No extracted content found. Try POST to extract first."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = ExtractedContentSerializer(content_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk, *args, **kwargs):
        try:
            pdf = UploadedPDF.objects.get(pk=pk)
        except UploadedPDF.DoesNotExist:
            return Response({"error": "PDF not found."}, status=status.HTTP_404_NOT_FOUND)

        result = pdf_extractor.extract_pdf(pdf.file.path)
        content_obj, _ = ExtractedContent.objects.update_or_create(
            pdf=pdf,
            defaults={
                "text": result['text'],
                "images": result['images'],
                "tables": result['tables']
            }
        )
        serializer = ExtractedContentSerializer(content_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GenerateOutlineView(APIView):
    """
    API to generate blog outline from extracted text.
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            content = ExtractedContent.objects.get(pdf__pk=pk)
            outline_data = outline.generate_outline(content.text)
            outline_obj = BlogOutline.objects.create(
                pdf=content.pdf,
                outline_json=outline_data
            )
            serializer = BlogOutlineSerializer(outline_obj)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ExtractedContent.DoesNotExist:
            return Response(
                {"error": "Extracted content not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class DraftSectionView(APIView):
    """
    API to draft blog sections.
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            outline_obj = BlogOutline.objects.get(pk=pk)
            section = request.data.get('section')
            context = ExtractedContent.objects.get(pdf=outline_obj.pdf).text
            body = writer.draft_section(section, context)
            draft_obj = BlogDraft.objects.create(
                outline=outline_obj,
                section_title=section['title'],
                content=body
            )
            serializer = BlogDraftSerializer(draft_obj)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except BlogOutline.DoesNotExist:
            return Response(
                {"error": "Outline not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except ExtractedContent.DoesNotExist:
            return Response(
                {"error": "Extracted content not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class FormatBlogView(APIView):
    """
    API to assemble and save final blog (HTML + PDF).
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            outline = BlogOutline.objects.get(pk=pk)
            drafts = BlogDraft.objects.filter(outline=outline)
            sections = [
                {"title": d.section_title, "body": d.content}
                for d in drafts
            ]
            html_content = formatter.assemble_html(sections, blog_title="My Blog")
            files = formatter.save_html_and_pdf(html_content, filename=f"blog_{pk}")
            return Response({
                "html_file": files['html_path'],
                "pdf_file": files['pdf_path']
            }, status=status.HTTP_200_OK)
        except BlogOutline.DoesNotExist:
            return Response(
                {"error": "Outline not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class ChatWithPDFView(APIView):
    """
    API to chat with PDF content.
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            pdf = UploadedPDF.objects.get(pk=pk)
            user_message = request.data.get('message')

            content = ExtractedContent.objects.get(pdf=pdf)
            chat_history = ChatMessage.objects.filter(pdf=pdf).order_by('timestamp')
            history_text = "\n".join([
                f"User: {c.user_message}\nAgent: {c.agent_response}"
                for c in chat_history
            ])

            context = (
                f"Extracted Text:\n{content.text}\n\n"
                f"Images:\n{content.images}\n\n"
                f"Tables:\n{content.tables}\n\n"
                f"Chat History:\n{history_text}"
            )

            from .services.api_handler import call_llm
            prompt = (
                "You are a helpful assistant. Answer questions about the PDF content.\n\n"
                f"{context}\n\n"
                f"User: {user_message}\nAgent:"
            )
            agent_response = call_llm(prompt, preferred="openai")

            chat_obj = ChatMessage.objects.create(
                pdf=pdf,
                user_message=user_message,
                agent_response=agent_response
            )
            serializer = ChatMessageSerializer(chat_obj)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except UploadedPDF.DoesNotExist:
            return Response(
                {"error": "PDF not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except ExtractedContent.DoesNotExist:
            return Response(
                {"error": "Extracted content not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class NormalizationRuleView(APIView):
    """
    API to list and add normalization rules.
    """
    def get(self, request):
        rules = NormalizationRule.objects.all()
        serializer = NormalizationRuleSerializer(rules, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = NormalizationRuleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Frontend page renderers

def upload_page(request):
    return render(request, 'upload.html')


def chat_page(request, pk):
    return render(request, 'chat.html', {'pdf_id': pk})


def blog_page(request, pk):
    return render(request, 'blog.html', {'pdf_id': pk})


def ppt_page(request, pk):
    return render(request, 'ppt.html', {'pdf_id': pk})


def poster_page(request, pk):
    return render(request, 'poster.html', {'pdf_id': pk})
