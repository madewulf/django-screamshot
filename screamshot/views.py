import base64
import logging
from io import BytesIO
import os.path
import tempfile
from django.core.urlresolvers import NoReverseMatch
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.translation import ugettext as _
import hashlib


from .utils import (casperjs_capture, CaptureError, UnsupportedImageFormat,
                    image_mimetype, parse_url)

logger = logging.getLogger(__name__)


def capture(request):
    # Merge both QueryDict into dict
    parameters = dict([(k, v) for k, v in request.GET.items()])
    parameters.update(dict([(k, v) for k, v in request.POST.items()]))
    method = parameters.get('method', request.method)
    selector = parameters.get('selector')
    data = parameters.get('data')
    waitfor = parameters.get('waitfor')
    wait = parameters.get('wait')
    render = parameters.get('render', 'png')
    size = parameters.get('size')
    crop = parameters.get('crop')

    url = parameters.get('url')
    m = hashlib.sha256()
    m.update(str(url).encode('utf-8'))
    url_md5 = m.hexdigest()
    temp_dir = tempfile.gettempdir()

    media_path = '%s/%s.png' % (temp_dir, url_md5)
    if os.path.isfile(media_path):
        f = open(media_path, 'rb')
        response = HttpResponse(content_type=image_mimetype(render))
        response.write(f.read())
        return response
    if not url:
        return HttpResponseBadRequest(_('Missing url parameter'))
    try:
        url = parse_url(request, url)
    except NoReverseMatch:
        error_msg = _("URL '%s' invalid (could not reverse)") % url
        return HttpResponseBadRequest(error_msg)



    try:
        width = int(parameters.get('width', ''))
    except ValueError:
        width = None
    try:
        height = int(parameters.get('height', ''))
    except ValueError:
        height = None

    stream = BytesIO()
    try:
        casperjs_capture(stream, url, method=method.lower(), width=width,
                         height=height, selector=selector, data=data,
                         size=size, waitfor=waitfor, crop=crop, render=render,
                         wait=wait)
    except CaptureError as e:
        return HttpResponseBadRequest(e)
    except ImportError:
        error_msg = _('Resize not supported (PIL not available)')
        return HttpResponseBadRequest(error_msg)
    except UnsupportedImageFormat:
        error_msg = _('Unsupported image format: %s' % render)
        return HttpResponseBadRequest(error_msg)

    if render == "html":
        response = HttpResponse(content_type='text/html')
        body = """<html><body onload="window.print();">
                <img src="data:image/png;base64,%s"/></body></html>
                """ % base64.encodestring(stream.getvalue())
        response.write(body)
    else:
        f = open(media_path, 'wb')
        f.write(stream.getvalue())
        f.close()
        response = HttpResponse(content_type=image_mimetype(render))
        response.write(stream.getvalue())

    return response
