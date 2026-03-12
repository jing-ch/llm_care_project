import json

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import serializers, services


@require_GET
def home(request):
    return render(request, 'careplan/form.html')


@csrf_exempt
@require_POST
def generate_careplan(request):
    body = json.loads(request.body)
    data = serializers.parse_generate_request(body)
    result = services.submit_careplan_request(data)
    return JsonResponse(result, status=202)


@require_GET
def get_careplan_status(request, care_plan_id):
    care_plan = services.get_careplan_by_id(care_plan_id)
    if care_plan is None:
        return JsonResponse({'error': 'not found'}, status=404)
    return JsonResponse(serializers.serialize_careplan_status(care_plan))


@require_GET
def get_careplan(request, care_plan_id):
    care_plan = services.get_careplan_by_id(care_plan_id)
    if care_plan is None:
        return JsonResponse({'error': 'not found'}, status=404)
    return JsonResponse(serializers.serialize_careplan(care_plan))


@require_GET
def search_careplans(request):
    q = (request.GET.get('q') or '').strip().lower()
    queryset = services.search_careplans(q)
    results = [serializers.serialize_careplan(cp) for cp in queryset]
    return JsonResponse({'results': results})


@require_GET
def download_careplan(request, care_plan_id):
    care_plan = services.get_careplan_for_download(care_plan_id)
    if care_plan is None:
        return JsonResponse({'error': 'not found'}, status=404)
    filename = services.build_download_filename(care_plan)
    response = HttpResponse(care_plan.content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
