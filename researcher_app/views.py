# researcher_app/views.py

#Backend
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


class UploadPDFView(APIView):
    """
    API to upload a PDF and immediately parse it.
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        print("DEBUG: request.data =", request.data)
        print("DEBUG: request.FILES =", request.FILES)

        serializer = UploadedPDFSerializer(data=request.data)
        if serializer.is_valid():
            pdf = serializer.save()
            try:
                # ✅ Parse PDF directly from uploaded file (request.FILES)
                uploaded_file = request.FILES.get('file')
                result = pdf_extractor.extract_pdf(uploaded_file)
                
                # ✅ Save extracted content to DB
                content_obj, created = ExtractedContent.objects.update_or_create(
                    pdf=pdf,
                    defaults={
                        "text": result.get('text', ''),
                        "images": result.get('images', []),
                        "tables": result.get('tables', [])
                    }
                )
                parse_status = "success"
            except Exception as e:
                print("ERROR parsing PDF:", e)
                parse_status = "failed"

            return Response({
                "id": pdf.id,
                "url": pdf.file.url,
                "parse_status": parse_status
            }, status=status.HTTP_201_CREATED)
        
        print("DEBUG: serializer errors =", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ExtractPDFView(APIView):
    """
    API to extract text, images, tables from uploaded PDF.
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            pdf = UploadedPDF.objects.get(pk=pk)
            result = pdf_extractor.extract_pdf(pdf.file.path)
            content_obj, created = ExtractedContent.objects.update_or_create(
                pdf=pdf,
                defaults={
                    "text": result['text'],
                    "images": result['images'],
                    "tables": result['tables']
                }
            )
            serializer = ExtractedContentSerializer(content_obj)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UploadedPDF.DoesNotExist:
            return Response({"error": "PDF not found."}, status=status.HTTP_404_NOT_FOUND)


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
            return Response({"error": "Extracted content not found."}, status=status.HTTP_404_NOT_FOUND)


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
            return Response({"error": "Outline not found."}, status=status.HTTP_404_NOT_FOUND)
        except ExtractedContent.DoesNotExist:
            return Response({"error": "Extracted content not found."}, status=status.HTTP_404_NOT_FOUND)


class FormatBlogView(APIView):
    """
    API to assemble and save final blog (HTML + PDF).
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            outline = BlogOutline.objects.get(pk=pk)
            drafts = BlogDraft.objects.filter(outline=outline)
            sections = [{"title": d.section_title, "body": d.content} for d in drafts]
            html_content = formatter.assemble_html(sections, blog_title="My Blog")
            files = formatter.save_html_and_pdf(html_content, filename=f"blog_{pk}")
            return Response({"html_file": files['html_path'], "pdf_file": files['pdf_path']}, status=status.HTTP_200_OK)
        except BlogOutline.DoesNotExist:
            return Response({"error": "Outline not found."}, status=status.HTTP_404_NOT_FOUND)


class ChatWithPDFView(APIView):
    """
    API to chat with PDF content.
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            pdf = UploadedPDF.objects.get(pk=pk)
            user_message = request.data.get('message')

            # Get context: extracted content + chat history
            content = ExtractedContent.objects.get(pdf=pdf)
            chat_history = ChatMessage.objects.filter(pdf=pdf).order_by('timestamp')
            history_text = "\n".join([f"User: {c.user_message}\nAgent: {c.agent_response}" for c in chat_history])

            # Combine context
            context = f"Extracted Text:\n{content.text}\n\nImages:\n{content.images}\n\nTables:\n{content.tables}\n\nChat History:\n{history_text}"

            # Call LLM
            from .services.api_handler import call_llm
            prompt = f"""You are a helpful assistant. Answer questions about the PDF content.\n\n{context}\n\nUser: {user_message}\nAgent:"""
            agent_response = call_llm(prompt, preferred="openai")

            # Save chat
            chat_obj = ChatMessage.objects.create(
                pdf=pdf,
                user_message=user_message,
                agent_response=agent_response
            )
            serializer = ChatMessageSerializer(chat_obj)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except UploadedPDF.DoesNotExist:
            return Response({"error": "PDF not found."}, status=status.HTTP_404_NOT_FOUND)
        except ExtractedContent.DoesNotExist:
            return Response({"error": "Extracted content not found."}, status=status.HTTP_404_NOT_FOUND)


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



#Frontend
from django.shortcuts import render

def upload_page(request):
    """
    Renders the upload page for PDFs.
    """
    return render(request, 'upload.html')

def chat_page(request, pk):
    """
    Renders the Chat with PDF page.
    """
    return render(request, 'chat.html', {'pdf_id': pk})


def blog_page(request, pk):
    """
    Renders the Blog creation page.
    """
    return render(request, 'blog.html', {'pdf_id': pk})


def ppt_page(request, pk):
    """
    Renders the PPT creation page.
    """
    return render(request, 'ppt.html', {'pdf_id': pk})


def poster_page(request, pk):
    """
    Renders the Poster creation page.
    """
    return render(request, 'poster.html', {'pdf_id': pk})
