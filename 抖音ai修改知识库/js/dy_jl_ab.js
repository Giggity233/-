const BitStr = {
    s0: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",
    s1: "Dkdpgh4ZKsQB80/Mfvw36XI1R25+WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
    s2: "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
    s3: "ckdp1h4ZKsUB80/Mfvw36XIgR25+WQAlEi7NLboqYTOPuzmFjJnryx9HVGDaStCe",
    s4: "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe",
    s5: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-."
};

function js_shift_left(x, y) {
    return (x << y) >>> 0;
}

function js_shift_right(x, y) {
    return (x >>> y) >>> 0;
}

function randomStr(num, type) {
    const chars = {
        int: "0123456789",
        str_lower: "abcdefghijklmnopqrstuvwxyz",
        str_upper: "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        str_all: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        int_str_lower: "0123456789abcdefghijklmnopqrstuvwxyz",
        int_str_upper: "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        int_str_all: "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        hex: "0123456789abcdef"
    };

    if (!chars[type]) {
        console.log("类型未定义");
        return "";
    }

    let result = '';
    const charSet = chars[type];

    for (let i = 0; i < num; i++) {
        result += charSet[Math.floor(Math.random() * charSet.length)];
    }

    return result;
}

function le(e, r) {
    return (js_shift_left(e, r % 32) | js_shift_right(e, 32 - (r % 32))) >>> 0;
}

function de(e) {
    if (0 <= e && e < 16) {
        return 2043430169;
    } else if (16 <= e && e < 64) {
        return 2055708042;
    } else {
        throw new Error("Invalid j for constant Tj");
    }
}

function pe(e, r, t, a) {
    if (0 <= e && e < 16) {
        return (r ^ t ^ a) >>> 0;
    } else if (16 <= e && e < 64) {
        return (r & t | r & a | t & a) >>> 0;
    } else {
        throw new Error("Invalid j for bool function FF");
    }
}

function he(e, r, t, a) {
    if (0 <= e && e < 16) {
        return (r ^ t ^ a) >>> 0;
    } else if (16 <= e && e < 64) {
        return (r & t | ~r & a) >>> 0;
    } else {
        throw new Error("Invalid j for bool function GG");
    }
}
class Reg {
    constructor() {
        this.chunk = [];
        this.reg = [
            1937774191,
            1226093241,
            388252375,
            3666478592,
            2842636476,
            372324522,
            3817729613,
            2969243214,
        ];
        this.size = 0;
    }

    write(e) {
        let f;
        if (typeof e === 'string') {
            f = [...e].map(char => char.charCodeAt(0));
        } else {
            f = e;
        }
        this.size += f.length;
        let i = 64 - this.chunk.length;

        if (f.length < i) {
            this.chunk.push(...f);
        } else {
            this.chunk.push(...f.slice(0, i));
            while (this.chunk.length >= 64) {
                this._compress(this.chunk);
                if (i < f.length) {
                    this.chunk = f.slice(i, Math.min(i + 64, f.length));
                } else {
                    this.chunk = [];
                }
                i += 64;
            }
        }
    }

    _compress(r) {
        if (r.length < 64) {
            throw new Error("Compress error: not enough data");
        } else {
            const w = new Array(132).fill(0);
            for (let t = 0; t < 16; t++) {
                w[t] |= js_shift_left(r[4 * t], 24);
                w[t] |= js_shift_left(r[4 * t + 1], 16);
                w[t] |= js_shift_left(r[4 * t + 2], 8);
                w[t] |= r[4 * t + 3];
                w[t] = js_shift_right(w[t], 0);
            }
            for (let a = 16; a < 68; a++) {
                let n = w[a - 16] ^ w[a - 9] ^ le(w[a - 3], 15);
                n = n ^ le(n, 15) ^ le(n, 23);
                w[a] = (n ^ le(w[a - 13], 7) ^ w[a - 6]) >>> 0;
            }
            for (let a = 0; a < 64; a++) {
                w[a + 68] = (w[a] ^ w[a + 4]) >>> 0;
            }
            let n = [...this.reg];
            for (let f = 0; f < 64; f++) {
                let i = le(n[0], 12) + n[4] + le(de(f), f);
                i = i >>> 0;
                i = le(js_shift_right(i, 0), 7);
                let o = js_shift_right(i ^ le(n[0], 12), 0);
                let c = pe(f, n[0], n[1], n[2]);
                c = (c + n[3] + o + w[f + 68]) >>> 0;
                let s = he(f, n[4], n[5], n[6]);
                s = (s + n[7] + i + w[f]) >>> 0;
                n[3] = n[2];
                n[2] = le(n[1], 9);
                n[1] = n[0];
                n[0] = c;
                n[7] = n[6];
                n[6] = le(n[5], 19);
                n[5] = n[4];
                n[4] = (s ^ le(s, 9) ^ le(s, 17)) >>> 0;
            }
            for (let u = 0; u < 8; u++) {
                this.reg[u] = (this.reg[u] ^ n[u]) >>> 0;
            }
        }
    }

    _fill() {
        let n = 8 * this.size;
        this.chunk.push(128);
        let f = this.chunk.length % 64;
        if (64 - f < 8) {
            f -= 64;
        }
        while (f < 56) {
            this.chunk.push(0);
            f++;
        }
        for (let i = 0; i < 4; i++) {
            let o = Math.floor(n / 4294967296);
            this.chunk.push(js_shift_right(o, 8 * (3 - i)) & 255);
        }
        for (let i = 0; i < 4; i++) {
            this.chunk.push(js_shift_right(n, 8 * (3 - i)) & 255);
        }
    }
}

function strToArrayAb(t, a) {
    const reg = new Reg();
    reg.write(t);
    reg._fill();
    for (let i = 0; i < reg.chunk.length; i += 64) {
        reg._compress(reg.chunk.slice(i, i + 64));
    }
    let o;
    if (a === "hex") {
        o = reg.reg.map(val => val.toString(16).padStart(8, '0')).join('');
    } else {
        o = new Array(32).fill(0);
        for (let i = 0; i < 8; i++) {
            let c = reg.reg[i];
            o[4 * i + 3] = c & 0xFF;
            c = js_shift_right(c, 8);
            o[4 * i + 2] = c & 0xFF;
            c = js_shift_right(c, 8);
            o[4 * i + 1] = c & 0xFF;
            c = js_shift_right(c, 8);
            o[4 * i] = c & 0xFF;
        }
    }
    return o;
}


function rc4Encrypt(key, plaintext) {
    const S = Array.from({ length: 256 }, (_, i) => i);
    let j = 0;

    for (let i = 0; i < 256; i++) {
        j = (j + S[i] + key.charCodeAt(i % key.length)) % 256;
        [S[i], S[j]] = [S[j], S[i]];
    }

    let out = '';
    let i = 0;
    j = 0;

    for (let char of plaintext) {
        i = (i + 1) % 256;
        j = (j + S[i]) % 256;
        [S[i], S[j]] = [S[j], S[i]];
        out += String.fromCharCode(char.charCodeAt(0) ^ S[(S[i] + S[j]) % 256]);
    }
    return out;
}

function bitwise(a1, a2, a3, s) {
    if (a1 !== "null" && a2 !== "null" && a3 !== "null") {
        let x1 = js_shift_left(a1.charCodeAt(0) & 255, 16);
        let x2 = js_shift_left(a2.charCodeAt(0) & 255, 8);
        let x3 = a3.charCodeAt(0);
        let x4 = x1 | x2 | x3;
        return (
            BitStr[s][js_shift_right((x4 & 16515072), 18)] +
            BitStr[s][js_shift_right((x4 & 258048), 12)] +
            BitStr[s][js_shift_right((x4 & 4032), 6)] +
            BitStr[s][x4 & 63]
        );
    } else {
        let x1 = js_shift_left(a1.charCodeAt(0) & 255, 16);
        let x4 = x1;
        return (
            BitStr[s][js_shift_right((x4 & 16515072), 18)] +
            BitStr[s][js_shift_right((x4 & 258048), 12)] +
            "==" // 修正为两个等号
        );
    }
}

function encryptTs(ts) {
    let n1 = ts & 255;
    let n2 = jsShiftRight(ts, 8) & 255;
    return [(n1 & 170) + 1, (n1 & 85) + 2, (n2 & 170) + 64, (n2 & 85) + 2];
}

function encryptTs1(ts) {
    ts *= 10000;
    let n1 = Math.floor(ts) & 255;
    let n2 = js_shift_right(Math.floor(ts), 8) & 255;
    return [
        (n1 & 170) | (3 & 85),
        (n1 & 85) | (3 & 170),
        (n2 & 170) | (45 & 85),
        (n2 & 85) | (45 & 170)
    ];
}

function encryptTs2(ts) {
    ts *= 10000;
    let n1 = Math.floor(ts) & 255;
    let n2 = js_shift_right(Math.floor(ts), 8) & 255;
    return [
        (n1 & 170) | (1 & 85),
        (n1 & 85) | (1 & 170),
        (n2 & 170) | (0 & 85),
        (n2 & 85) | (0 & 170)
    ];
}

function encryptTs3(ts) {
    ts *= 10000;
    let n1 = Math.floor(ts) & 255;
    let n2 = js_shift_right(Math.floor(ts), 8) & 255;
    return [
        (n1 & 170) | (1 & 85),
        (n1 & 85) | (1 & 170),
        (n2 & 170) | (1 & 85),
        (n2 & 85) | (1 & 170)
    ];
}

class ABogus {
    constructor() {
        this.ts1 = null;
        this.ts2 = null;
        this.ts3 = 397.22701604035683;
        this.ts4 = null;
        this.ts5 = null;
        this.ts6 = null;
        this.pageId = 0;
        this.aid = 1128;
        this.pd_salt = "cus";
        this.user_agent_salt = [0.00390625, 1, 0]; // ubcode
        this.rc4_key_ua = String.fromCharCode(0, 1, 0);
        this.rc4_key_ab = "\x79";
    }

    getABogus(user_agent, param, data = null) {
        if (!this.ts1) {
            this.ts2 = Math.floor(Date.now()) - 300;
            this.ts1 = Math.floor(Date.now()) - 100;
        }

        param += this.pd_salt;
        const param_array = strToArrayAb(strToArrayAb(param));
        console.log(param_array)
        if (data !== null) {
            data += this.pd_salt;
        } else {
            data = "";
        }
        const data_array = strToArrayAb(strToArrayAb(data));
        console.log(data_array)
        const ua_rc4 = rc4Encrypt(this.rc4_key_ua, user_agent);
        let ua_str = "";
        for (let i = 0; i < ua_rc4.length; i += 3) {
            ua_str += bitwise(ua_rc4[i], ua_rc4[i + 1], ua_rc4[i + 2], "s3");
        }
        const ua_array = strToArrayAb(ua_str);

        const new_array = [];
        new_array.push(44);
        new_array.push(
            (this.ts1 >> 24) & 255, 0, 0, 0, 0, 4,
            param_array[21], data_array[21], 0, ua_array[23],
            (this.ts1 >> 16) & 255, 0, this.pageId >> 8, this.pageId & 255,
            1, 0, this.aid & 255,
            param_array[22],
            data_array[22],
            ua_array[24],
            (this.ts1 >> 8) & 255, 0, 0, 0, 0,
            this.ts1 & 255, 0, 0,
            this.user_agent_salt[this.user_agent_salt.length - 1],
            (this.ts2 >> 24) & 255,
            (this.ts2 >> 16) & 255, 0,
            (this.ts2 >> 8) & 255,
            this.ts2 & 255,
            3,
            Math.floor(this.ts3),
            Math.floor(this.ts3 / 256),
            Math.floor(this.ts3),
            Math.floor(this.ts3 / 256),
            67, 0, 0, 0
        );

        const array_last = new_array.reduce((x, y) => x ^ y, 0);
        new_array.push(50, 50, 52, 48, 124, 49, 53, 48, 124, 50, 50, 52,
            48, 124, 49, 51, 54, 48, 124, 48, 124, 48, 124, 48, 124, 48,
            124, 50, 50, 52, 48, 124, 49, 51, 54, 48, 124, 50, 50, 52,
            48, 124, 49, 52, 48, 48, 124, 50, 50, 52, 48, 124, 49, 53,
            48, 124, 50, 52, 124, 50, 52, 124, 87, 105, 110, 51, 50);
        new_array.push(array_last);

        if (!this.ts4) {
            this.ts4 = parseFloat("0." + randomStr(16, "int"));
            this.ts5 = parseFloat("0." + randomStr(16, "int"));
            this.ts6 = parseFloat("0." + randomStr(16, "int"));
        }

        const part1_array = encryptTs1(this.ts4);
        const part1_bytes = String.fromCharCode(...part1_array);
        const part2_array = encryptTs2(this.ts5);
        const part2_bytes = String.fromCharCode(...part2_array);
        const part3_array = encryptTs3(this.ts6);
        const part3_bytes = String.fromCharCode(...part3_array);

        const part4_bytes = String.fromCharCode(...new_array);
        const encrypted_part4 = rc4Encrypt(this.rc4_key_ab, part4_bytes);

        let ab_bytes = part1_bytes + part2_bytes + part3_bytes + encrypted_part4;
        let abogus = "";
        for (let i = 0; i < ab_bytes.length; i += 3) {
            if (i + 2 < ab_bytes.length) {
                abogus += bitwise(ab_bytes[i], ab_bytes[i+1], ab_bytes[i+2], "s4");
            } else if (i + 1 < ab_bytes.length) {
                abogus += bitwise(ab_bytes[i], ab_bytes[i+1], "null", "s4");
            } else {
                abogus += bitwise(ab_bytes[i], "null", "null", "s4");
            }
        }
        return abogus;
    }
}

// const ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
// const url = 'is_h5=1&origin_type=638301&device_platform=webapp&aid=6383&channel=channel_pc_web&pc_client_type=1&pc_libra_divert=Windows&update_version_code=170400&version_code=&version_name=&cookie_enabled=true&screen_width=1536&screen_height=864&browser_language=zh-CN&browser_platform=Win32&browser_name=Chrome&browser_version=126.0.0.0&browser_online=true&engine_name=Blink&engine_version=126.0.0.0&os_name=Windows&os_version=10&cpu_core_num=16&device_memory=8&platform=PC&downlink=10&effective_type=4g&round_trip_time=50&webid=7395285928674330149&msToken=rbsQDVzP6VXnDKNVC_JWFgKmMRe-HflKubBCuDdpi39KpPvYagtRJyvcsRfNo5NCug4klvP2iZcoWjTeBXx9Syy5X2hdstM3lXoV_wvPh-fABdmsCITBFUzheN1vJAuMd205Mwy9gqghmOuBfXGMVGueeV56q347dob6qJ8GSYG7lOPBqGSG3g%3D%3D';
// const data = 'bff_type=2&ec_promotion_id=3701250906063561211&is_h5=1&live_room_id=7416953239968533260&origin_type=638301&promotion_ids=3701250906063561211&room_id=7416953239968533260&sec_author_id=MS4wLjABAAAAJkrhp2hvmFTLy0saQ68nNN1GqK2sCSAd1WRoO8VoxgQkxRHpCZ_ssMMK8cjpxeZo&use_new_price=1';
// const abogus = new ABogus().getABogus(
//         ua,
//         url,
//         data
//     );
function enc(url,data,ua) {
    const abogus = new ABogus().getABogus(
        ua,
        url,
        data
    );
    return abogus
}
// url = 'urls=https%3A%2F%2Fhaohuo.jinritemai.com%2Fecommerce%2Ftrade%2Fdetail%2Findex.html%3Fid%3D3745447888117957060%26origin_type%3Dpc_buyin_selection_decision%26request_from%3D203%26scene%3D1&request_from=203&scene=1&verifyFp=verify_mac1ybvr_keNczMBq_bzJR_4e8L_9pSr_C9hfZScQIUfz&fp=verify_mac1ybvr_keNczMBq_bzJR_4e8L_9pSr_C9hfZScQIUfz&msToken=aOyQhv9uxfbkPc5B6DfltDH0JWMKy-fwjUuoW_ZKHHy-p9KeZFHu5BG8lk1v9Y868gQu9t17UT0HbZxAiGK3pIhcfhas3H5Cae1obb28woiS19ji3XHepK4wM9kgJOxe0rppGG-sqcl8vk09tuvJ7yC2UETN73L2ZxNnmvZp3fqT'
// data = '{"scene":"PCSquareFeed","size":30,"search_text":"","cursor":0,"extra":{"new_session_strategy":"1","search_id":"aa24da9302e20cc7b55a30b05a408c19e42ebeb36048c207df0b02ee9ebf877e00f59982250bac29a07ef115d159e4a24565411ec6c501468ac53cfe2ab90923636c627c9d6f8255f741944b24274be1","session_id":"2240ef2d8a855155c5a83bb0482ffccf197cd99dd99017347d914442b8d79bf1ccddd1f0f915ee2c660a28217e6bd5dd387580684f40d9df7328e91a72e7e22f0a4074205df3083e6aea1c9531b67bda","use_kol_product":"0"},"filters":{"BusinessCid":{"value":["7"]},"alliance_sales_30d":{"value":["R:5000,-"]},"FeaturedItems":{"value":["is_first_onshelf_prod_30d"]}}}'
// userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
// // console.log(abogus);
// console.log(enc(url,null,userAgent))