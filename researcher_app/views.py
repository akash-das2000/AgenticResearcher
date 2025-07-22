# researcher_app/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from .models import (
    UploadedPDF, ExtractedContent, BlogOutline, BlogDraft, ChatMessage, NormalizationRule, Feedback
)
from .serializers import (
    UploadedPDFSerializer, ExtractedContentSerializer,
    BlogOutlineSerializer, BlogDraftSerializer,
    ChatMessageSerializer, NormalizationRuleSerializer
)
from .services import pdf_extractor, outline, writer, formatter, outline
from io import BytesIO
import tempfile
import threading
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse
from django.conf import settings
import os
from django import forms
from researcher_app.services.rag_service import RAGService




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
    API to generate or refine a blog outline.
    - POST /api/outline/<outline_id>/ with no body → fresh generate
    - POST /api/outline/<outline_id>/ with JSON {"feedback": "..."} → refine
    """
    def post(self, request, pk, *args, **kwargs):
        # 1) Load the existing BlogOutline
        outline_obj = get_object_or_404(BlogOutline, pk=pk)

        # 2) Grab the extracted text
        content = get_object_or_404(ExtractedContent, pdf=outline_obj.pdf)

        # 3) Decide whether to generate or refine
        fb = request.data.get("feedback", None)
        if fb:
            new_json = outline.refine_outline(outline_obj.outline_json, fb)
        else:
            new_json = outline.generate_outline(content.text)

        # 4) Save & return
        outline_obj.outline_json = new_json
        outline_obj.status       = "finalized"
        outline_obj.save()
        serializer = BlogOutlineSerializer(outline_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)
            


class DraftSectionView(APIView):
    """
    API to draft or refine blog sections.
    """
    def post(self, request, pk, *args, **kwargs):
        # 1) Lookup the outline
        outline_obj = get_object_or_404(BlogOutline, pk=pk)

        # 2) Must have a section_id for an existing draft
        draft_id = request.data.get("section_id")
        if not draft_id:
            raise ParseError(detail="`section_id` is required")

        # 3) Fetch the BlogDraft
        draft_obj = get_object_or_404(BlogDraft, pk=draft_id, outline=outline_obj)

        # 4) Grab full extracted text
        context = get_object_or_404(ExtractedContent, pdf=outline_obj.pdf).text

        # 5) Pull the corresponding section info from the outline JSON
        sections = outline_obj.outline_json.get("sections", [])
        try:
            sec_info = sections[draft_obj.section_order]
        except (IndexError, TypeError):
            raise ParseError(detail="Invalid section_order on draft")

        # 6) Safely parse feedback (it may be null in the JSON)
        raw_fb = request.data.get("feedback")
        feedback = (raw_fb or "").strip()

        # 7) Decide whether to generate or refine
        if feedback:
            # refine existing draft
            new_body = writer.refine_section(
                draft_obj.section_title,
                draft_obj.content,
                feedback
            )
        else:
            # first‐time generation
            new_body = writer.draft_section(sec_info, context)

        # 8) Save and return
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


class MetaSectionView(APIView):
    """
    API to generate or refine only the blog DESCRIPTION.
    """
    def post(self, request, pk, *args, **kwargs):
        outline = get_object_or_404(BlogOutline, pk=pk)
        context = get_object_or_404(ExtractedContent, pdf=outline.pdf).text

        raw_fb = request.data.get("feedback")
        fb     = (raw_fb or "").strip()

        if fb:
            desc = writer.refine_description(outline, fb, context)
        else:
            desc = writer.generate_description(outline, context)

        return Response({"description": desc}, status=status.HTTP_200_OK)
        


class ChatWithPDFView(APIView):
    """
    POST /api/chat/pdf/<pdf_id>/
    Body: { "question": "What is the main contribution?" }
    """
    def post(self, request, pdf_id):
        # 1) Verify the PDF exists
        try:
            pdf = UploadedPDF.objects.get(pk=pdf_id)
        except UploadedPDF.DoesNotExist:
            return Response(
                {"error": "PDF not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 2) Pull the user’s question
        question = request.data.get("question", "").strip()
        if not question:
            return Response(
                {"error": "No question provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3) Run RAG
        svc = RAGService(pdf_id)
        svc.build_index()                # embed & index
        hits = svc.retrieve(question, k=3)
        answer = svc.ask_gemini(hits, question)

        # 4) Return structured JSON
        return Response({
            "answer": answer,
            "hits": hits
        })


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
# New “Make a Blog” workflow views (steps 2–5)
# —————————————————————————————————————————

def new_blog(request, pdf_id):
    """
    Step 1 (launcher):
    Create a placeholder BlogOutline (no LLM call yet),
    then redirect into the outline‐refine page where
    the real outline generation will happen via the API.
    """
    pdf = get_object_or_404(UploadedPDF, id=pdf_id)
    # Ensure the PDF has been parsed
    content = get_object_or_404(ExtractedContent, pdf=pdf)

    # 1) Create an outline record with empty JSON & pending status
    outline_obj = BlogOutline.objects.create(
        pdf=pdf,
        outline_json={},       # no content yet
        status="pending"       # mark as waiting for generation
    )

    # 2) Redirect immediately into the outline phase
    return redirect("outline_refine", outline_id=outline_obj.id)


def outline_refine(request, outline_id):
    """
    Step 1: show the generated outline, let the user tweak it,
    record every tweak in Feedback, and once ‘Looks Good’ is clicked,
    finalize the outline and create empty drafts for each section.
    """
    outline_obj = get_object_or_404(BlogOutline, id=outline_id)

    if request.method == "POST":
        feedback_text = request.POST.get("feedback", "").strip()

        # 1) Log the feedback (section_order=None for outline)
        Feedback.objects.create(
            outline=outline_obj,
            section_order=None,
            text=feedback_text
        )

        # 2) If they clicked “Looks Good” (name="feedback" value="OK")
        if request.POST.get("feedback") == "OK":
            outline_obj.status = "finalized"
            outline_obj.save()

            # Seed a BlogDraft for each section in the outline JSON
            sections = outline_obj.outline_json.get("sections", [])
            for idx, sec in enumerate(sections):
                BlogDraft.objects.create(
                    outline=outline_obj,
                    section_order=idx,
                    section_title=sec["title"],
                    content=""  # will be generated in section_write
                )

            # Jump into the first section
            return redirect("section_write", outline_id=outline_obj.id)

        # 3) Otherwise (“Apply Feedback”) → re-generate the outline
        updated_outline = outline.refine_outline(
            outline_obj.outline_json,
            feedback_text
        )
        outline_obj.outline_json = updated_outline
        outline_obj.save()

    # On GET (or after a refinement), re–render the page
    feedbacks = outline_obj.feedbacks.filter(section_order=None)
    sections  = outline_obj.outline_json.get("sections", [])

    return render(request, "blog/outline_refine.html", {
        "outline":   outline_obj,
        "sections":  sections,
        "feedbacks": feedbacks,
        "outline_id":  outline_id, 
    })



def section_write(request, outline_id):
    """
    Step 3: Loop through each BlogDraft:
    – On GET: if content is blank, call writer.draft_section(...)
      and save it.
    – Render the draft + feedback box.
    – On POST: if feedback is “OK”, mark is_final; else call writer.refine_section(...)
      and re‐save, then reload.
    """
    outline_obj = get_object_or_404(BlogOutline, id=outline_id)

    # next unfinished section
    draft = (
        outline_obj.drafts
        .filter(is_final=False)
        .order_by("section_order")
        .first()
    )

    # if all sections are done, move on
    if not draft:
        return redirect("blog_meta", outline_id=outline_id)

    # grab the full extracted text for reference
    full_text = get_object_or_404(ExtractedContent, pdf=outline_obj.pdf).text

    if request.method == "POST":
        fb = request.POST.get("feedback", "").strip()
        if fb.lower() in ("ok", "looks good", "no changes"):
            draft.is_final = True
            draft.save()
        else:
            # apply a refinement pass
            draft.content = writer.refine_section(
                draft.section_title,
                draft.content,
                fb
            )
            draft.save()
        # reload to either show next section or updated content
        return redirect("section_write", outline_id=outline_id)

    # First‐time GET: generate the draft if empty
    if not draft.content:
        sec_info = outline_obj.outline_json["sections"][draft.section_order]
        draft.content = writer.draft_section(sec_info, full_text)
        draft.save()

    # === NEW: pull in any past tweak requests for this section ===
    feedbacks = outline_obj.feedbacks.filter(section_order=draft.section_order)

    return render(request, "blog/section_write.html", {
        "draft": draft,
        "feedbacks": feedbacks,
    })


class BlogMetaForm(forms.Form):
    title       = forms.CharField(max_length=200, required=False, label="Blog Title")
    author_name = forms.CharField(max_length=100, required=False, label="Author Name")

def blog_meta(request, outline_id):
    """
    Step: collect title & author before finalizing.
    """
    outline = get_object_or_404(BlogOutline, id=outline_id)

    if request.method == "POST":
        form = BlogMetaForm(request.POST)
        if form.is_valid():
            outline.title       = form.cleaned_data["title"]
            outline.author_name = form.cleaned_data["author_name"]
            outline.save()
            return redirect("blog_finish", outline_id=outline_id)
    else:
        form = BlogMetaForm(initial={
            "title":       outline.title,
            "author_name": outline.author_name
        })

    return render(request, "blog/blog_meta.html", {
        "form":       form,
        "outline_id": outline_id,
    })



def blog_finish(request, outline_id):
    # 1) Fetch outline & all its section drafts
    outline = get_object_or_404(BlogOutline, id=outline_id)
    drafts = outline.drafts.order_by("section_order")
    sections = [
        {"title": d.section_title, "body": d.content}
        for d in drafts
    ]

    # 2) Assemble the full blog HTML
    html_content = formatter.assemble_html(
        sections,
        blog_title=outline.title or "Untitled Blog",
        author=(request.user.username if request.user.is_authenticated else "Anonymous")
    )

    # 3) Save out HTML & PDF to MEDIA_ROOT
    files = formatter.save_html_and_pdf(
        html_content,
        filename=f"blog_{outline.id}"
    )
    # files == {'html_path': '/app/media/blog_5.html', 'pdf_path': '/app/media/blog_5.pdf'}

    # 4) Build public URLs (if you need them elsewhere)
    html_url = settings.MEDIA_URL + os.path.basename(files['html_path'])
    pdf_url  = settings.MEDIA_URL + os.path.basename(files['pdf_path'])

    # 5) Render final template with everything it needs
    return render(request, "blog/blog_finish.html", {
        "outline_id": outline_id,     # for your {% url 'blog_preview' outline_id=outline_id %}
        "blog_html":  html_content,   # the full, scrollable blog
        "html_url":   html_url,       # (optional) direct HTML download link
        "pdf_url":    pdf_url,        # (optional) direct PDF download link
    })

def blog_preview(request, outline_id):
    """
    Renders the assembled blog HTML inline for previewing.
    """
    outline = get_object_or_404(BlogOutline, id=outline_id)
    drafts = outline.drafts.order_by("section_order")
    sections = [
        {"title": d.section_title, "body": d.content}
        for d in drafts
    ]
    html_content = formatter.assemble_html(
        sections,
        blog_title=outline.title or "Untitled Blog",
        author=outline.author_name or "Anonymous"
    )
    return HttpResponse(html_content)

# —————————————————————————————————————————
# Codes for Chat with PDF
# —————————————————————————————————————————

def chat_with_pdf(request, pdf_id):
    question = request.POST["question"]
    svc = RAGService(pdf_id)
    svc.build_index()
    hits = svc.retrieve(question, k=3)
    answer = svc.ask_gemini(hits, question)
    return JsonResponse({"answer": answer, "hits": hits})


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
