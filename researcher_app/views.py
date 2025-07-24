# researcher_app/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from .models import (
    UploadedPDF, ExtractedContent, BlogOutline, BlogDraft,
    ChatMessage, NormalizationRule, Feedback
)
from .serializers import (
    UploadedPDFSerializer, ExtractedContentSerializer,
    BlogOutlineSerializer, BlogDraftSerializer,
    ChatMessageSerializer, NormalizationRuleSerializer
)
from .services import pdf_extractor, outline, writer, formatter
import tempfile
import threading
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django import forms
from researcher_app.services.rag_service import RAGService
from .services.pdf_extractor import extract_pdf
from os.path import basename



def parse_pdf_async(pdf_id, file_path):
    try:
        # 1) extract
        result = extract_pdf(file_path)
        pdf = UploadedPDF.objects.get(id=pdf_id)
        ExtractedContent.objects.create(
            pdf=pdf,
            text=result["text"],
            images=result["images"],
            tables=result["tables"],
        )
        print("✅ Saved extracted content to DB")

        # 2) build & persist index once
        svc = RAGService(pdf_id)
        svc.build_index(persist=True)
        print(f"✅ Built & cached FAISS index for PDF {pdf_id}")
    except Exception as e:
        print(f"❌ parse_pdf_async failed for PDF {pdf_id}: {e}")


class UploadPDFView(APIView):
    """
    API to upload a PDF and parse in background.
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file provided."},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = UploadedPDFSerializer(data=request.data)
        if serializer.is_valid():
            pdf = serializer.save()
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
            return Response({"error": "PDF not found."},
                            status=status.HTTP_404_NOT_FOUND)

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
    API to generate or refine a blog outline.
    """
    def post(self, request, pk, *args, **kwargs):
        outline_obj = get_object_or_404(BlogOutline, pk=pk)
        content = get_object_or_404(ExtractedContent, pdf=outline_obj.pdf)
        fb = request.data.get("feedback", None)
        if fb:
            new_json = outline.refine_outline(outline_obj.outline_json, fb)
        else:
            new_json = outline.generate_outline(content.text)

        outline_obj.outline_json = new_json
        outline_obj.status = "finalized"
        outline_obj.save()
        serializer = BlogOutlineSerializer(outline_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DraftSectionView(APIView):
    """
    API to draft or refine blog sections.
    """
    def post(self, request, pk, *args, **kwargs):
        outline_obj = get_object_or_404(BlogOutline, pk=pk)
        draft_id = request.data.get("section_id")
        if not draft_id:
            return Response({"error": "`section_id` is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        draft_obj = get_object_or_404(BlogDraft, pk=draft_id, outline=outline_obj)
        context = get_object_or_404(ExtractedContent, pdf=outline_obj.pdf).text
        sections = outline_obj.outline_json.get("sections", [])
        try:
            sec_info = sections[draft_obj.section_order]
        except (IndexError, TypeError):
            return Response({"error": "Invalid section_order on draft."},
                            status=status.HTTP_400_BAD_REQUEST)

        raw_fb = request.data.get("feedback")
        feedback = (raw_fb or "").strip()
        if feedback:
            new_body = writer.refine_section(
                draft_obj.section_title,
                draft_obj.content,
                feedback
            )
        else:
            new_body = writer.draft_section(sec_info, context)

        draft_obj.content = new_body
        draft_obj.save()
        serializer = BlogDraftSerializer(draft_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FormatBlogView(APIView):
    """
    API to assemble and save final blog (HTML + PDF).
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            outline_obj = BlogOutline.objects.get(pk=pk)
            drafts = BlogDraft.objects.filter(outline=outline_obj)
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


class MetaSectionView(APIView):
    """
    API to generate or refine only the blog DESCRIPTION.
    """
    def post(self, request, pk, *args, **kwargs):
        outline_obj = get_object_or_404(BlogOutline, pk=pk)
        context = get_object_or_404(ExtractedContent, pdf=outline_obj.pdf).text
        raw_fb = request.data.get("feedback")
        fb = (raw_fb or "").strip()
        if fb:
            desc = writer.refine_description(outline_obj, fb, context)
        else:
            desc = writer.generate_description(outline_obj, context)
        return Response({"description": desc}, status=status.HTTP_200_OK)


class ChatWithPDFView(APIView):
    def post(self, request, pdf_id):
        question = request.data.get("question", "").strip()
        if not question:
            return Response({"error": "No question provided."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            svc    = RAGService(pdf_id)
            hits   = svc.retrieve(question, k=3)
            answer = svc.ask_gemini(hits, question)
            return Response({"answer": answer, "hits": hits})
        except Exception as e:
            print(f"❌ Chat error for PDF {pdf_id}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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


# —————————————————————————————————————————
# “Make a Blog” workflow views (steps 2–5)
# —————————————————————————————————————————

def new_blog(request, pdf_id):
    pdf = get_object_or_404(UploadedPDF, id=pdf_id)
    content = get_object_or_404(ExtractedContent, pdf=pdf)
    outline_obj = BlogOutline.objects.create(
        pdf=pdf,
        outline_json={},
        status="pending"
    )
    return redirect("outline_refine", outline_id=outline_obj.id)


def outline_refine(request, outline_id):
    outline_obj = get_object_or_404(BlogOutline, id=outline_id)
    if request.method == "POST":
        feedback_text = request.POST.get("feedback", "").strip()
        Feedback.objects.create(
            outline=outline_obj,
            section_order=None,
            text=feedback_text
        )
        if request.POST.get("feedback") == "OK":
            outline_obj.status = "finalized"
            outline_obj.save()
            sections = outline_obj.outline_json.get("sections", [])
            for idx, sec in enumerate(sections):
                BlogDraft.objects.create(
                    outline=outline_obj,
                    section_order=idx,
                    section_title=sec["title"],
                    content=""
                )
            return redirect("section_write", outline_id=outline_obj.id)
        updated_outline = outline.refine_outline(
            outline_obj.outline_json, feedback_text
        )
        outline_obj.outline_json = updated_outline
        outline_obj.save()

    feedbacks = outline_obj.feedbacks.filter(section_order=None)
    sections = outline_obj.outline_json.get("sections", [])
    return render(request, "blog/outline_refine.html", {
        "outline": outline_obj,
        "sections": sections,
        "feedbacks": feedbacks,
        "outline_id": outline_id,
    })


def section_write(request, outline_id):
    outline_obj = get_object_or_404(BlogOutline, id=outline_id)
    draft = outline_obj.drafts.filter(is_final=False).order_by("section_order").first()
    if not draft:
        return redirect("blog_meta", outline_id=outline_id)

    full_text = get_object_or_404(ExtractedContent, pdf=outline_obj.pdf).text

    if request.method == "POST":
        fb = request.POST.get("feedback", "").strip()
        if fb.lower() in ("ok", "looks good", "no changes"):
            draft.is_final = True
            draft.save()
        else:
            draft.content = writer.refine_section(
                draft.section_title, draft.content, fb
            )
            draft.save()
        return redirect("section_write", outline_id=outline_id)

    if not draft.content:
        sec_info = outline_obj.outline_json["sections"][draft.section_order]
        draft.content = writer.draft_section(sec_info, full_text)
        draft.save()

    feedbacks = outline_obj.feedbacks.filter(section_order=draft.section_order)
    return render(request, "blog/section_write.html", {
        "draft": draft,
        "feedbacks": feedbacks,
    })


class BlogMetaForm(forms.Form):
    title       = forms.CharField(max_length=200, required=False, label="Blog Title")
    author_name = forms.CharField(max_length=100, required=False, label="Author Name")


def blog_meta(request, outline_id):
    outline_obj = get_object_or_404(BlogOutline, id=outline_id)
    if request.method == "POST":
        form = BlogMetaForm(request.POST)
        if form.is_valid():
            outline_obj.title = form.cleaned_data["title"]
            outline_obj.author_name = form.cleaned_data["author_name"]
            outline_obj.save()
            return redirect("blog_finish", outline_id=outline_id)
    else:
        form = BlogMetaForm(initial={
            "title": outline_obj.title,
            "author_name": outline_obj.author_name
        })
    return render(request, "blog/blog_meta.html", {
        "form": form,
        "outline_id": outline_id,
    })


def blog_finish(request, outline_id):
    outline_obj = get_object_or_404(BlogOutline, id=outline_id)
    drafts = outline_obj.drafts.order_by("section_order")
    sections = [{"title": d.section_title, "body": d.content} for d in drafts]
    html_content = formatter.assemble_html(
        sections,
        blog_title=outline_obj.title or "Untitled Blog",
        author=(request.user.username if request.user.is_authenticated else "Anonymous")
    )
    files = formatter.save_html_and_pdf(
        html_content, filename=f"blog_{outline_obj.id}"
    )
    html_url = settings.MEDIA_URL + os.path.basename(files['html_path'])
    pdf_url = settings.MEDIA_URL + os.path.basename(files['pdf_path'])
    return render(request, "blog/blog_finish.html", {
        "outline_id": outline_id,
        "blog_html": html_content,
        "html_url": html_url,
        "pdf_url": pdf_url,
    })


def blog_preview(request, outline_id):
    outline_obj = get_object_or_404(BlogOutline, id=outline_id)
    drafts = outline_obj.drafts.order_by("section_order")
    sections = [{"title": d.section_title, "body": d.content} for d in drafts]
    html_content = formatter.assemble_html(
        sections,
        blog_title=outline_obj.title or "Untitled Blog",
        author=outline_obj.author_name or "Anonymous"
    )
    return HttpResponse(html_content)


# Frontend page renderers

def upload_page(request):
    return render(request, 'upload.html')


def chat_page(request, pdf_id):
    pdf = get_object_or_404(UploadedPDF, pk=pdf_id)
    title = basename(pdf.file.name)      # strip the “uploads/” prefix
    return render(request, 'chat_with_pdf.html', {
        'pdf_id': pdf_id,
        'pdf_title': title,
    })


def blog_page(request, pk):
    return render(request, 'blog.html', {'pdf_id': pk})


def ppt_page(request, pk):
    return render(request, 'ppt.html', {'pdf_id': pk})


def poster_page(request, pk):
    return render(request, 'poster.html', {'pdf_id': pk})
