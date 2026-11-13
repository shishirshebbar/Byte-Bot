"""Bounded multipart parsing with bytearrays only: no temporary files."""
import json
import re
from python_multipart import MultipartParser
from python_multipart.multipart import parse_options_header
from .ocr import EvidenceError, FILE_LIMIT

BODY_LIMIT = 6 * 1024 * 1024


async def read_body(request, limit):
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise EvidenceError(413, 'evidence_too_large', 'The submitted evidence is too large.')
        body.extend(chunk)
    return bytes(body)


async def json_body(request):
    try:
        return json.loads(await read_body(request, 65536))
    except (ValueError, UnicodeError):
        raise EvidenceError(422, 'invalid_input', 'Check the supplied field values.') from None


async def screenshot_body(request):
    media, options = parse_options_header(request.headers.get('content-type', ''))
    boundary = options.get(b'boundary', b'')
    if media != b'multipart/form-data' or not 1 <= len(boundary) <= 200:
        raise EvidenceError(422, 'invalid_upload', 'Submit one screenshot and its expected revision.')
    body = await read_body(request, BODY_LIMIT)
    parts, current, header, done = [], {}, [bytearray(), bytearray()], [False]

    def begin():
        if len(parts) >= 2:
            raise ValueError()
        current.clear()
        current.update(headers={}, data=bytearray())

    def header_end():
        key = bytes(header[0]).lower()
        if key in current['headers']:
            raise ValueError()
        current['headers'][key] = bytes(header[1])
        header[0].clear()
        header[1].clear()

    def data(chunk, start, end):
        if len(current['data']) + end - start > FILE_LIMIT:
            raise EvidenceError(413, 'evidence_too_large', 'Use an image up to 5 MiB.')
        current['data'].extend(chunk[start:end])

    callbacks = {
        'on_part_begin': begin,
        'on_header_field': lambda data, start, end: header[0].extend(data[start:end]),
        'on_header_value': lambda data, start, end: header[1].extend(data[start:end]),
        'on_header_end': header_end,
        'on_part_data': data,
        'on_part_end': lambda: parts.append(dict(current)),
        'on_end': lambda: done.__setitem__(0, True),
    }
    try:
        parser = MultipartParser(boundary, callbacks)
        parser.write(body)
        parser.finalize()
        if not done[0] or len(parts) != 2:
            raise ValueError()
        fields = {}
        for part in parts:
            disposition, opts = parse_options_header(part['headers'].get(b'content-disposition', b''))
            name = opts.get(b'name')
            if disposition != b'form-data' or name not in (b'file', b'expected_revision') or name in fields:
                raise ValueError()
            fields[name] = part
        raw_revision = bytes(fields[b'expected_revision']['data'])
        if not re.fullmatch(rb'[0-9]{1,10}', raw_revision):
            raise ValueError()
        image = fields[b'file']
        return bytes(image['data']), image['headers'].get(b'content-type', b'').decode('ascii'), int(raw_revision)
    except EvidenceError:
        raise
    except Exception:
        raise EvidenceError(422, 'invalid_upload', 'Submit one screenshot and its expected revision.') from None
