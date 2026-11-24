import base64
import zlib
import re
import json



class Reader:
    def __init__(self, buf):
        self.buf = buf
        self.pos = 0
        self.len = len(buf)

    def uint32(self):
        u = shift = 0
        while True:
            b = self.buf[self.pos]
            self.pos += 1
            u |= (b & 0x7F) << shift
            if b < 0x80:
                return u
            shift += 7
            if shift > 35:
                raise Exception("Too many bytes for uint32")

    def skip(self, length=None):
        if length is None:
            while self.buf[self.pos] & 0x80:
                self.pos += 1
            self.pos += 1
        else:
            self.pos += length

    def skip_type(self, t):
        if t == 0:
            self.skip()
        elif t == 1:
            self.skip(8)
        elif t == 2:
            length = self.uint32()
            self.skip(length)
        elif t == 3:
            while True:
                wire_type = self.uint32() & 7
                if wire_type == 4:
                    break
                self.skip_type(wire_type)
        elif t == 5:
            self.skip(4)
        else:
            raise ValueError("Unknown wire type")

    def read_bytes(self):
        length = self.uint32()
        start = self.pos
        end = start + length
        self.pos = end
        return self.buf[start:end]

    def read_string(self):
        return self.read_bytes().decode("utf-8")

    def read_uint64(self):
        # Read varint (max 10 bytes)
        result = 0
        shift = 0
        for _ in range(10):
            b = self.buf[self.pos]
            self.pos += 1
            result |= ((b & 0x7F) << shift)
            if b < 128:
                return result
            shift += 7
        raise Exception("Invalid varint")


def base64_to_bytes(b64):
    return base64.b64decode(b64)


def ungzip(data):
    return zlib.decompress(data, zlib.MAX_WBITS | 16)  # gzip header


def gt_decode(buf):
    r = Reader(buf)
    result = {}

    while r.pos < r.len:
        tag = r.uint32()
        field_num = tag >> 3
        wire_type = tag & 0x7

        if field_num == 1:  # command
            result['command'] = r.read_string()
        elif field_num == 2:  # protocol
            result['protocol'] = r.uint32()
        elif field_num == 3:  # errorCode
            result['errorCode'] = r.uint32()
        elif field_num == 4:  # bizCode
            result['bizCode'] = r.uint32()
        elif field_num == 5:  # bizErrorMsg
            result['bizErrorMsg'] = r.read_string()
        elif field_num == 6:  # compress
            result['compress'] = r.uint32()
        elif field_num == 9:  # extension
            result['extension'] = r.read_bytes()
        elif field_num == 10:  # body
            result['body'] = r.read_bytes()
        elif field_num in (11, 12, 13):  # uint64
            key = {11: 'downstreamSeq', 12: 'conId', 13: 'ctxId'}[field_num]
            result[key] = r.read_uint64()
        else:
            r.skip_type(wire_type)

    return result


def run11(base64_data):
    full_array = base64_to_bytes(base64_data)
    offset_array = full_array[16:]  # skip header
    decoded = gt_decode(offset_array)

    if decoded.get("compress") == 1 and isinstance(decoded.get("body"), bytes):
        decoded["body"] = ungzip(decoded["body"])

    return decoded




def decode_extension_bytes(extension_dict):
    """
    从 Protobuf 的 extension 字段（字节数组表示成 key-value 格式）中解码 UTF-8 字符串。

    参数：
        extension_dict (dict): 如 {"0": 10, "1": 9, "2": 49, ...} 的字典，键是字符串数字，值是 0~255 的字节。

    返回：
        str: UTF-8 解码的字符串，
    """
    sorted_keys = sorted(extension_dict, key=lambda x: int(x))
    byte_values = [extension_dict[k] for k in sorted_keys]
    byte_data = bytes(byte_values)

    try:
        decoded = byte_data.decode('utf-8')
    except UnicodeDecodeError:
        decoded = byte_data.decode('utf-8', errors='replace')

    visible = ''.join(c for c in decoded if c.isprintable())


    return visible



def parse_body_bytes(body_bytes):
    try:
        matches = re.findall(b'(\{.*})', body_bytes, re.DOTALL)
        if not matches:
            raise ValueError("找不到 JSON 结构")

        for match in matches:
            try:
                # 尝试将该片段转为 JSON 对象
                return json.loads(match.decode('utf-8'))
            except Exception:
                continue

        raise ValueError("所有匹配都无法解析为 JSON")

    except Exception as e:
        return None


def run(res):
    try:
        b64 = res['payloadData']
        try:
            data = json.loads(b64)
            return data
        except:
            extension_data =run11(b64)['body']
            # 1. 提取 JSON 数据
            parsed_result = parse_body_bytes(extension_data)
            data = json.dumps(parsed_result, indent=2, ensure_ascii=False)
            return data
    except Exception as e:
        pass



