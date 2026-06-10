from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET

from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import serializers, services


@require_GET
def home(request):
    # Plain Django view: serves the HTML form, not a JSON API.
    return render(request, 'careplan/form.html')


@api_view(['POST'])
def generate_careplan(request):
    s = serializers.GenerateRequestSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    result = services.submit_careplan_request(s.validated_data)
    return Response(result, status=202)


@api_view(['GET'])
def get_careplan_status(request, care_plan_id):
    care_plan = services.get_careplan_by_id(care_plan_id)
    if care_plan is None:
        return Response({'error': 'not found'}, status=404)
    return Response(serializers.serialize_careplan_status(care_plan))


@api_view(['GET'])
def get_careplan(request, care_plan_id):
    care_plan = services.get_careplan_by_id(care_plan_id)
    if care_plan is None:
        return Response({'error': 'not found'}, status=404)
    return Response(serializers.serialize_careplan(care_plan))


@api_view(['GET'])
def search_careplans(request):
    q = (request.query_params.get('q') or '').strip().lower()
    queryset = services.search_careplans(q)
    results = [serializers.serialize_careplan(cp) for cp in queryset]
    return Response({'results': results})


@require_GET
def download_careplan(request, care_plan_id):
    # Plain Django view: returns a .txt file attachment, not JSON.
    care_plan = services.get_careplan_for_download(care_plan_id)
    if care_plan is None:
        return JsonResponse({'error': 'not found'}, status=404)
    filename = services.build_download_filename(care_plan)
    response = HttpResponse(care_plan.content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
