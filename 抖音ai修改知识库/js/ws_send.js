const protobuf = require("protobufjs/minimal");
const $Writer = protobuf.Writer;
const $util = protobuf.util;




const $root = {
    "im_proto": {
        "Request": function() {
                function e(e) {
                    if (this.headers = {},
                    e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.cmd = 0,
                e.prototype.sequence_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.sdk_version = "",
                e.prototype.token = "",
                e.prototype.refer = 0,
                e.prototype.inbox_type = 0,
                e.prototype.build_number = "",
                e.prototype.body = null,
                e.prototype.device_id = "",
                e.prototype.channel = "",
                e.prototype.device_platform = "",
                e.prototype.device_type = "",
                e.prototype.os_version = "",
                e.prototype.version_code = "",
                e.prototype.headers = $util.emptyObject,
                e.prototype.config_id = 0,
                e.prototype.token_info = null,
                e.prototype.auth_type = 0,
                e.prototype.msg_trace = null,
                e.prototype.retry_count = 0,
                e.prototype.biz = "",
                e.prototype.access = "",
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    if (t || (t = $Writer.create()),
                    null != e.cmd && Object.hasOwnProperty.call(e, "cmd") && t.uint32(8).int32(e.cmd),
                    null != e.sequence_id && Object.hasOwnProperty.call(e, "sequence_id") && t.uint32(16).int64(e.sequence_id),
                    null != e.sdk_version && Object.hasOwnProperty.call(e, "sdk_version") && t.uint32(26).string(e.sdk_version),
                    null != e.token && Object.hasOwnProperty.call(e, "token") && t.uint32(34).string(e.token),
                    null != e.refer && Object.hasOwnProperty.call(e, "refer") && t.uint32(40).int32(e.refer),
                    null != e.inbox_type && Object.hasOwnProperty.call(e, "inbox_type") && t.uint32(48).int32(e.inbox_type),
                    null != e.build_number && Object.hasOwnProperty.call(e, "build_number") && t.uint32(58).string(e.build_number),
                    null != e.body && Object.hasOwnProperty.call(e, "body") && $root.im_proto.RequestBody.encode(e.body, t.uint32(66).fork()).ldelim(),
                    null != e.device_id && Object.hasOwnProperty.call(e, "device_id") && t.uint32(74).string(e.device_id),
                    null != e.channel && Object.hasOwnProperty.call(e, "channel") && t.uint32(82).string(e.channel),
                    null != e.device_platform && Object.hasOwnProperty.call(e, "device_platform") && t.uint32(90).string(e.device_platform),
                    null != e.device_type && Object.hasOwnProperty.call(e, "device_type") && t.uint32(98).string(e.device_type),
                    null != e.os_version && Object.hasOwnProperty.call(e, "os_version") && t.uint32(106).string(e.os_version),
                    null != e.version_code && Object.hasOwnProperty.call(e, "version_code") && t.uint32(114).string(e.version_code),
                    null != e.headers && Object.hasOwnProperty.call(e, "headers"))
                        for (var n = Object.keys(e.headers), r = 0; r < n.length; ++r)
                            t.uint32(122).fork().uint32(10).string(n[r]).uint32(18).string(e.headers[n[r]]).ldelim();
                    return null != e.config_id && Object.hasOwnProperty.call(e, "config_id") && t.uint32(128).int32(e.config_id),
                    null != e.token_info && Object.hasOwnProperty.call(e, "token_info") && $root.im_proto.TokenInfo.encode(e.token_info, t.uint32(138).fork()).ldelim(),
                    null != e.auth_type && Object.hasOwnProperty.call(e, "auth_type") && t.uint32(144).int32(e.auth_type),
                    null != e.msg_trace && Object.hasOwnProperty.call(e, "msg_trace") && $root.im_proto.MsgTrace.encode(e.msg_trace, t.uint32(154).fork()).ldelim(),
                    null != e.retry_count && Object.hasOwnProperty.call(e, "retry_count") && t.uint32(160).int32(e.retry_count),
                    null != e.biz && Object.hasOwnProperty.call(e, "biz") && t.uint32(170).string(e.biz),
                    null != e.access && Object.hasOwnProperty.call(e, "access") && t.uint32(178).string(e.access),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n, r, o = void 0 === t ? e.len : e.pos + t, i = new $root.im_proto.Request; e.pos < o; ) {
                        var a = e.uint32();
                        switch (a >>> 3) {
                        case 1:
                            i.cmd = e.int32();
                            break;
                        case 2:
                            i.sequence_id = e.int64();
                            break;
                        case 3:
                            i.sdk_version = e.string();
                            break;
                        case 4:
                            i.token = e.string();
                            break;
                        case 5:
                            i.refer = e.int32();
                            break;
                        case 6:
                            i.inbox_type = e.int32();
                            break;
                        case 7:
                            i.build_number = e.string();
                            break;
                        case 8:
                            i.body = $root.im_proto.RequestBody.decode(e, e.uint32());
                            break;
                        case 9:
                            i.device_id = e.string();
                            break;
                        case 10:
                            i.channel = e.string();
                            break;
                        case 11:
                            i.device_platform = e.string();
                            break;
                        case 12:
                            i.device_type = e.string();
                            break;
                        case 13:
                            i.os_version = e.string();
                            break;
                        case 14:
                            i.version_code = e.string();
                            break;
                        case 15:
                            i.headers === $util.emptyObject && (i.headers = {});
                            var s = e.uint32() + e.pos;
                            for (n = "",
                            r = ""; e.pos < s; ) {
                                var c = e.uint32();
                                switch (c >>> 3) {
                                case 1:
                                    n = e.string();
                                    break;
                                case 2:
                                    r = e.string();
                                    break;
                                default:
                                    e.skipType(7 & c)
                                }
                            }
                            i.headers[n] = r;
                            break;
                        case 16:
                            i.config_id = e.int32();
                            break;
                        case 17:
                            i.token_info = $root.im_proto.TokenInfo.decode(e, e.uint32());
                            break;
                        case 18:
                            i.auth_type = e.int32();
                            break;
                        case 19:
                            i.msg_trace = $root.im_proto.MsgTrace.decode(e, e.uint32());
                            break;
                        case 20:
                            i.retry_count = e.int32();
                            break;
                        case 21:
                            i.biz = e.string();
                            break;
                        case 22:
                            i.access = e.string();
                            break;
                        default:
                            e.skipType(7 & a)
                        }
                    }
                    return i
                }
                ,
                e
            }(),
        "Frame": function() {
                function e(e) {
                    if (this.headers = [],
                    e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.seqid = $util.Long ? $util.Long.fromBits(0, 0, !0) : 0,
                e.prototype.logid = $util.Long ? $util.Long.fromBits(0, 0, !0) : 0,
                e.prototype.service = 0,
                e.prototype.method = 0,
                e.prototype.headers = $util.emptyArray,
                e.prototype.payload_encoding = "",
                e.prototype.payload_type = "",
                e.prototype.payload = $util.newBuffer([]),
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    if (t || (t = $Writer.create()),
                    t.uint32(8).uint64(e.seqid),
                    t.uint32(16).uint64(e.logid),
                    t.uint32(24).int32(e.service),
                    t.uint32(32).int32(e.method),
                    null != e.headers && e.headers.length)
                        for (var n = 0; n < e.headers.length; ++n)
                            $root.im_proto.Frame.ExtendedEntry.encode(e.headers[n], t.uint32(42).fork()).ldelim();
                    return null != e.payload_encoding && Object.hasOwnProperty.call(e, "payload_encoding") && t.uint32(50).string(e.payload_encoding),
                    null != e.payload_type && Object.hasOwnProperty.call(e, "payload_type") && t.uint32(58).string(e.payload_type),
                    null != e.payload && Object.hasOwnProperty.call(e, "payload") && t.uint32(66).bytes(e.payload),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.Frame; e.pos < n; ) {
                        var o = e.uint32();
                        switch (o >>> 3) {
                        case 1:
                            r.seqid = e.uint64();
                            break;
                        case 2:
                            r.logid = e.uint64();
                            break;
                        case 3:
                            r.service = e.int32();
                            break;
                        case 4:
                            r.method = e.int32();
                            break;
                        case 5:
                            r.headers && r.headers.length || (r.headers = []),
                            r.headers.push($root.im_proto.Frame.ExtendedEntry.decode(e, e.uint32()));
                            break;
                        case 6:
                            r.payload_encoding = e.string();
                            break;
                        case 7:
                            r.payload_type = e.string();
                            break;
                        case 8:
                            r.payload = e.bytes();
                            break;
                        default:
                            e.skipType(7 & o)
                        }
                    }
                    if (!r.hasOwnProperty("seqid"))
                        throw $util.ProtocolError("missing required 'seqid'", {
                            instance: r
                        });
                    if (!r.hasOwnProperty("logid"))
                        throw $util.ProtocolError("missing required 'logid'", {
                            instance: r
                        });
                    if (!r.hasOwnProperty("service"))
                        throw $util.ProtocolError("missing required 'service'", {
                            instance: r
                        });
                    if (!r.hasOwnProperty("method"))
                        throw $util.ProtocolError("missing required 'method'", {
                            instance: r
                        });
                    return r
                }
                ,
                e.ExtendedEntry = function() {
                    function e(e) {
                        if (e)
                            for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                                null != e[t[n]] && (this[t[n]] = e[t[n]])
                    }
                    return e.prototype.key = "",
                    e.prototype.value = "",
                    e.create = function(t) {
                        return new e(t)
                    }
                    ,
                    e.encode = function(e, t) {
                        return t || (t = $Writer.create()),
                        t.uint32(10).string(e.key),
                        t.uint32(18).string(e.value),
                        t
                    }
                    ,
                    e.decode = function(e, t) {
                        e instanceof $Reader || (e = $Reader.create(e));
                        for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.Frame.ExtendedEntry; e.pos < n; ) {
                            var o = e.uint32();
                            switch (o >>> 3) {
                            case 1:
                                r.key = e.string();
                                break;
                            case 2:
                                r.value = e.string();
                                break;
                            default:
                                e.skipType(7 & o)
                            }
                        }
                        if (!r.hasOwnProperty("key"))
                            throw $util.ProtocolError("missing required 'key'", {
                                instance: r
                            });
                        if (!r.hasOwnProperty("value"))
                            throw $util.ProtocolError("missing required 'value'", {
                                instance: r
                            });
                        return r
                    }
                    ,
                    e
                }(),
                e
            }(),
        "RequestBody":function() {
                function e(e) {
                    if (e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.send_message_body = null,
                e.prototype.messages_per_user_body = null,
                e.prototype.messages_per_user_init_v2_body = null,
                e.prototype.get_message_by_id_body = null,
                e.prototype.messages_in_conversation_body = null,
                e.prototype.send_user_action_body = null,
                e.prototype.send_input_status_body = null,
                e.prototype.delete_conversation_body = null,
                e.prototype.mark_conversation_read_body = null,
                e.prototype.conversation_participants_body = null,
                e.prototype.dissolve_conversation_body = null,
                e.prototype.create_sub_conversation_body = null,
                e.prototype.get_sub_conversation_body = null,
                e.prototype.get_sub_conversation_list_body = null,
                e.prototype.get_conversation_info_v2_body = null,
                e.prototype.create_conversation_v2_body = null,
                e.prototype.get_conversation_info_list_v2_body = null,
                e.prototype.get_conversation_info_list_by_favorite_v2_body = null,
                e.prototype.get_conversation_info_list_by_top_v2_body = null,
                e.prototype.conversation_add_participants_body = null,
                e.prototype.conversation_remove_participants_body = null,
                e.prototype.leave_conversation_body = null,
                e.prototype.update_conversation_participant_body = null,
                e.prototype.delete_message_body = null,
                e.prototype.recall_message_body = null,
                e.prototype.modify_message_property_body = null,
                e.prototype.get_conversation_core_info_body = null,
                e.prototype.set_conversation_core_info_body = null,
                e.prototype.upsert_conversation_core_ext_info_body = null,
                e.prototype.set_conversation_setting_info_body = null,
                e.prototype.upsert_conversation_setting_ext_info_body = null,
                e.prototype.participants_read_index_body = null,
                e.prototype.participants_min_index_body = null,
                e.prototype.get_ticket_body = null,
                e.prototype.get_conversation_list_body = null,
                e.prototype.client_ack_body = null,
                e.prototype.report_client_metrics_body = null,
                e.prototype.get_configs_body = null,
                e.prototype.unread_count_report_body = null,
                e.prototype.modify_message_ext_body = null,
                e.prototype.get_unread_count_body = null,
                e.prototype.send_message_p2p_body = null,
                e.prototype.get_message_info_by_index_v2_body = null,
                e.prototype.batch_get_conversation_participants_readindex = null,
                e.prototype.get_message_info_by_index_v2_range_body = null,
                e.prototype.get_open_convs_body = null,
                e.prototype.get_messages_by_user_with_open_convs_body = null,
                e.prototype.get_user_message_with_open_convs_body = null,
                e.prototype.get_user_conversations_by_tag_body = null,
                e.prototype.set_user_all_conversations_settings_body = null,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    return t || (t = $Writer.create()),
                    null != e.send_message_body && Object.hasOwnProperty.call(e, "send_message_body") && $root.im_proto.SendMessageRequestBody.encode(e.send_message_body, t.uint32(802).fork()).ldelim(),
                    null != e.messages_per_user_body && Object.hasOwnProperty.call(e, "messages_per_user_body") && $root.im_proto.MessagesPerUserRequestBody.encode(e.messages_per_user_body, t.uint32(1602).fork()).ldelim(),
                    null != e.messages_per_user_init_v2_body && Object.hasOwnProperty.call(e, "messages_per_user_init_v2_body") && $root.im_proto.MessagesPerUserInitV2RequestBody.encode(e.messages_per_user_init_v2_body, t.uint32(1626).fork()).ldelim(),
                    null != e.get_message_by_id_body && Object.hasOwnProperty.call(e, "get_message_by_id_body") && $root.im_proto.GetMessageByIdRequestBody.encode(e.get_message_by_id_body, t.uint32(1690).fork()).ldelim(),
                    null != e.messages_in_conversation_body && Object.hasOwnProperty.call(e, "messages_in_conversation_body") && $root.im_proto.MessagesInConversationRequestBody.encode(e.messages_in_conversation_body, t.uint32(2410).fork()).ldelim(),
                    null != e.send_user_action_body && Object.hasOwnProperty.call(e, "send_user_action_body") && $root.im_proto.SendUserActionRequestBody.encode(e.send_user_action_body, t.uint32(3282).fork()).ldelim(),
                    null != e.send_input_status_body && Object.hasOwnProperty.call(e, "send_input_status_body") && $root.im_proto.SendInputStatusRequestBody.encode(e.send_input_status_body, t.uint32(3290).fork()).ldelim(),
                    null != e.delete_conversation_body && Object.hasOwnProperty.call(e, "delete_conversation_body") && $root.im_proto.DeleteConversationRequestBody.encode(e.delete_conversation_body, t.uint32(4826).fork()).ldelim(),
                    null != e.mark_conversation_read_body && Object.hasOwnProperty.call(e, "mark_conversation_read_body") && $root.im_proto.MarkConversationReadRequestBody.encode(e.mark_conversation_read_body, t.uint32(4834).fork()).ldelim(),
                    null != e.conversation_participants_body && Object.hasOwnProperty.call(e, "conversation_participants_body") && $root.im_proto.ConversationParticipantsListRequestBody.encode(e.conversation_participants_body, t.uint32(4842).fork()).ldelim(),
                    null != e.get_conversation_info_v2_body && Object.hasOwnProperty.call(e, "get_conversation_info_v2_body") && $root.im_proto.GetConversationInfoV2RequestBody.encode(e.get_conversation_info_v2_body, t.uint32(4866).fork()).ldelim(),
                    null != e.create_conversation_v2_body && Object.hasOwnProperty.call(e, "create_conversation_v2_body") && $root.im_proto.CreateConversationV2RequestBody.encode(e.create_conversation_v2_body, t.uint32(4874).fork()).ldelim(),
                    null != e.get_conversation_info_list_v2_body && Object.hasOwnProperty.call(e, "get_conversation_info_list_v2_body") && $root.im_proto.GetConversationInfoListV2RequestBody.encode(e.get_conversation_info_list_v2_body, t.uint32(4882).fork()).ldelim(),
                    null != e.get_conversation_info_list_by_favorite_v2_body && Object.hasOwnProperty.call(e, "get_conversation_info_list_by_favorite_v2_body") && $root.im_proto.ConversationsPerUserByFavoriteV2RequestBody.encode(e.get_conversation_info_list_by_favorite_v2_body, t.uint32(4890).fork()).ldelim(),
                    null != e.get_conversation_info_list_by_top_v2_body && Object.hasOwnProperty.call(e, "get_conversation_info_list_by_top_v2_body") && $root.im_proto.ConversationsPerUserByTopV2RequestBody.encode(e.get_conversation_info_list_by_top_v2_body, t.uint32(4898).fork()).ldelim(),
                    null != e.dissolve_conversation_body && Object.hasOwnProperty.call(e, "dissolve_conversation_body") && $root.im_proto.DissolveConversationRequestBody.encode(e.dissolve_conversation_body, t.uint32(4914).fork()).ldelim(),
                    null != e.create_sub_conversation_body && Object.hasOwnProperty.call(e, "create_sub_conversation_body") && $root.im_proto.CreateSubConversationRequestBody.encode(e.create_sub_conversation_body, t.uint32(4930).fork()).ldelim(),
                    null != e.get_sub_conversation_body && Object.hasOwnProperty.call(e, "get_sub_conversation_body") && $root.im_proto.GetSubConversationRequestBody.encode(e.get_sub_conversation_body, t.uint32(4938).fork()).ldelim(),
                    null != e.get_sub_conversation_list_body && Object.hasOwnProperty.call(e, "get_sub_conversation_list_body") && $root.im_proto.GetSubConversationListRequestBody.encode(e.get_sub_conversation_list_body, t.uint32(4946).fork()).ldelim(),
                    null != e.conversation_add_participants_body && Object.hasOwnProperty.call(e, "conversation_add_participants_body") && $root.im_proto.ConversationAddParticipantsRequestBody.encode(e.conversation_add_participants_body, t.uint32(5202).fork()).ldelim(),
                    null != e.conversation_remove_participants_body && Object.hasOwnProperty.call(e, "conversation_remove_participants_body") && $root.im_proto.ConversationRemoveParticipantsRequestBody.encode(e.conversation_remove_participants_body, t.uint32(5210).fork()).ldelim(),
                    null != e.leave_conversation_body && Object.hasOwnProperty.call(e, "leave_conversation_body") && $root.im_proto.ConversationLeaveRequestBody.encode(e.leave_conversation_body, t.uint32(5218).fork()).ldelim(),
                    null != e.update_conversation_participant_body && Object.hasOwnProperty.call(e, "update_conversation_participant_body") && $root.im_proto.UpdateConversationParticipantRequestBody.encode(e.update_conversation_participant_body, t.uint32(5242).fork()).ldelim(),
                    null != e.delete_message_body && Object.hasOwnProperty.call(e, "delete_message_body") && $root.im_proto.DeleteMessageRequestBody.encode(e.delete_message_body, t.uint32(5610).fork()).ldelim(),
                    null != e.recall_message_body && Object.hasOwnProperty.call(e, "recall_message_body") && $root.im_proto.RecallMessageRequestBody.encode(e.recall_message_body, t.uint32(5618).fork()).ldelim(),
                    null != e.modify_message_property_body && Object.hasOwnProperty.call(e, "modify_message_property_body") && $root.im_proto.ModifyMessagePropertyRequestBody.encode(e.modify_message_property_body, t.uint32(5642).fork()).ldelim(),
                    null != e.get_conversation_core_info_body && Object.hasOwnProperty.call(e, "get_conversation_core_info_body") && $root.im_proto.GetConversationCoreInfoRequestBody.encode(e.get_conversation_core_info_body, t.uint32(7210).fork()).ldelim(),
                    null != e.set_conversation_core_info_body && Object.hasOwnProperty.call(e, "set_conversation_core_info_body") && $root.im_proto.SetConversationCoreInfoRequestBody.encode(e.set_conversation_core_info_body, t.uint32(7218).fork()).ldelim(),
                    null != e.upsert_conversation_core_ext_info_body && Object.hasOwnProperty.call(e, "upsert_conversation_core_ext_info_body") && $root.im_proto.UpsertConversationCoreExtInfoRequestBody.encode(e.upsert_conversation_core_ext_info_body, t.uint32(7234).fork()).ldelim(),
                    null != e.set_conversation_setting_info_body && Object.hasOwnProperty.call(e, "set_conversation_setting_info_body") && $root.im_proto.SetConversationSettingInfoRequestBody.encode(e.set_conversation_setting_info_body, t.uint32(7370).fork()).ldelim(),
                    null != e.upsert_conversation_setting_ext_info_body && Object.hasOwnProperty.call(e, "upsert_conversation_setting_ext_info_body") && $root.im_proto.UpsertConversationSettingExtInfoRequestBody.encode(e.upsert_conversation_setting_ext_info_body, t.uint32(7378).fork()).ldelim(),
                    null != e.participants_read_index_body && Object.hasOwnProperty.call(e, "participants_read_index_body") && $root.im_proto.GetConversationParticipantsReadIndexV3RequestBody.encode(e.participants_read_index_body, t.uint32(16002).fork()).ldelim(),
                    null != e.participants_min_index_body && Object.hasOwnProperty.call(e, "participants_min_index_body") && $root.im_proto.GetConversationParticipantsMinIndexV3RequestBody.encode(e.participants_min_index_body, t.uint32(16010).fork()).ldelim(),
                    null != e.get_ticket_body && Object.hasOwnProperty.call(e, "get_ticket_body") && $root.im_proto.GetTicketRequestBody.encode(e.get_ticket_body, t.uint32(16042).fork()).ldelim(),
                    null != e.get_conversation_list_body && Object.hasOwnProperty.call(e, "get_conversation_list_body") && $root.im_proto.GetUserConversationListRequestBody.encode(e.get_conversation_list_body, t.uint32(16050).fork()).ldelim(),
                    null != e.client_ack_body && Object.hasOwnProperty.call(e, "client_ack_body") && $root.im_proto.ClientACKRequestBody.encode(e.client_ack_body, t.uint32(16082).fork()).ldelim(),
                    null != e.report_client_metrics_body && Object.hasOwnProperty.call(e, "report_client_metrics_body") && $root.im_proto.ReportClientMetricsRequestBody.encode(e.report_client_metrics_body, t.uint32(16130).fork()).ldelim(),
                    null != e.get_configs_body && Object.hasOwnProperty.call(e, "get_configs_body") && $root.im_proto.GetConfigsRequestBody.encode(e.get_configs_body, t.uint32(16138).fork()).ldelim(),
                    null != e.unread_count_report_body && Object.hasOwnProperty.call(e, "unread_count_report_body") && $root.im_proto.UnReadCountReportRequestBody.encode(e.unread_count_report_body, t.uint32(16146).fork()).ldelim(),
                    null != e.modify_message_ext_body && Object.hasOwnProperty.call(e, "modify_message_ext_body") && $root.im_proto.ModifyMessageExtRequestBody.encode(e.modify_message_ext_body, t.uint32(16170).fork()).ldelim(),
                    null != e.get_unread_count_body && Object.hasOwnProperty.call(e, "get_unread_count_body") && $root.im_proto.GetUnreadCountRequestBody.encode(e.get_unread_count_body, t.uint32(16242).fork()).ldelim(),
                    null != e.send_message_p2p_body && Object.hasOwnProperty.call(e, "send_message_p2p_body") && $root.im_proto.SendMessageP2PRequestBody.encode(e.send_message_p2p_body, t.uint32(16250).fork()).ldelim(),
                    null != e.get_message_info_by_index_v2_body && Object.hasOwnProperty.call(e, "get_message_info_by_index_v2_body") && $root.im_proto.GetMessageInfoByIndexV2RequestBody.encode(e.get_message_info_by_index_v2_body, t.uint32(16282).fork()).ldelim(),
                    null != e.batch_get_conversation_participants_readindex && Object.hasOwnProperty.call(e, "batch_get_conversation_participants_readindex") && $root.im_proto.BatchGetConversationParticipantsReadIndexRequestBody.encode(e.batch_get_conversation_participants_readindex, t.uint32(16306).fork()).ldelim(),
                    null != e.get_message_info_by_index_v2_range_body && Object.hasOwnProperty.call(e, "get_message_info_by_index_v2_range_body") && $root.im_proto.GetMessageInfoByIndexV2RangeRequestBody.encode(e.get_message_info_by_index_v2_range_body, t.uint32(16330).fork()).ldelim(),
                    null != e.get_open_convs_body && Object.hasOwnProperty.call(e, "get_open_convs_body") && $root.im_proto.GetOpenConvsRequestBody.encode(e.get_open_convs_body, t.uint32(128010).fork()).ldelim(),
                    null != e.get_messages_by_user_with_open_convs_body && Object.hasOwnProperty.call(e, "get_messages_by_user_with_open_convs_body") && $root.im_proto.GetMessagesByUserWithOpenConvsRequestBody.encode(e.get_messages_by_user_with_open_convs_body, t.uint32(128018).fork()).ldelim(),
                    null != e.get_user_message_with_open_convs_body && Object.hasOwnProperty.call(e, "get_user_message_with_open_convs_body") && $root.im_proto.GetUserMessageWithOpenConvsRequestBody.encode(e.get_user_message_with_open_convs_body, t.uint32(128026).fork()).ldelim(),
                    null != e.get_user_conversations_by_tag_body && Object.hasOwnProperty.call(e, "get_user_conversations_by_tag_body") && $root.im_proto.GetUserConversationsByTagRequestBody.encode(e.get_user_conversations_by_tag_body, t.uint32(136010).fork()).ldelim(),
                    null != e.set_user_all_conversations_settings_body && Object.hasOwnProperty.call(e, "set_user_all_conversations_settings_body") && $root.im_proto.SetUserAllConversationsSettingsRequestBody.encode(e.set_user_all_conversations_settings_body, t.uint32(136018).fork()).ldelim(),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.RequestBody; e.pos < n; ) {
                        var o = e.uint32();
                        switch (o >>> 3) {
                        case 100:
                            r.send_message_body = $root.im_proto.SendMessageRequestBody.decode(e, e.uint32());
                            break;
                        case 200:
                            r.messages_per_user_body = $root.im_proto.MessagesPerUserRequestBody.decode(e, e.uint32());
                            break;
                        case 203:
                            r.messages_per_user_init_v2_body = $root.im_proto.MessagesPerUserInitV2RequestBody.decode(e, e.uint32());
                            break;
                        case 211:
                            r.get_message_by_id_body = $root.im_proto.GetMessageByIdRequestBody.decode(e, e.uint32());
                            break;
                        case 301:
                            r.messages_in_conversation_body = $root.im_proto.MessagesInConversationRequestBody.decode(e, e.uint32());
                            break;
                        case 410:
                            r.send_user_action_body = $root.im_proto.SendUserActionRequestBody.decode(e, e.uint32());
                            break;
                        case 411:
                            r.send_input_status_body = $root.im_proto.SendInputStatusRequestBody.decode(e, e.uint32());
                            break;
                        case 603:
                            r.delete_conversation_body = $root.im_proto.DeleteConversationRequestBody.decode(e, e.uint32());
                            break;
                        case 604:
                            r.mark_conversation_read_body = $root.im_proto.MarkConversationReadRequestBody.decode(e, e.uint32());
                            break;
                        case 605:
                            r.conversation_participants_body = $root.im_proto.ConversationParticipantsListRequestBody.decode(e, e.uint32());
                            break;
                        case 614:
                            r.dissolve_conversation_body = $root.im_proto.DissolveConversationRequestBody.decode(e, e.uint32());
                            break;
                        case 616:
                            r.create_sub_conversation_body = $root.im_proto.CreateSubConversationRequestBody.decode(e, e.uint32());
                            break;
                        case 617:
                            r.get_sub_conversation_body = $root.im_proto.GetSubConversationRequestBody.decode(e, e.uint32());
                            break;
                        case 618:
                            r.get_sub_conversation_list_body = $root.im_proto.GetSubConversationListRequestBody.decode(e, e.uint32());
                            break;
                        case 608:
                            r.get_conversation_info_v2_body = $root.im_proto.GetConversationInfoV2RequestBody.decode(e, e.uint32());
                            break;
                        case 609:
                            r.create_conversation_v2_body = $root.im_proto.CreateConversationV2RequestBody.decode(e, e.uint32());
                            break;
                        case 610:
                            r.get_conversation_info_list_v2_body = $root.im_proto.GetConversationInfoListV2RequestBody.decode(e, e.uint32());
                            break;
                        case 611:
                            r.get_conversation_info_list_by_favorite_v2_body = $root.im_proto.ConversationsPerUserByFavoriteV2RequestBody.decode(e, e.uint32());
                            break;
                        case 612:
                            r.get_conversation_info_list_by_top_v2_body = $root.im_proto.ConversationsPerUserByTopV2RequestBody.decode(e, e.uint32());
                            break;
                        case 650:
                            r.conversation_add_participants_body = $root.im_proto.ConversationAddParticipantsRequestBody.decode(e, e.uint32());
                            break;
                        case 651:
                            r.conversation_remove_participants_body = $root.im_proto.ConversationRemoveParticipantsRequestBody.decode(e, e.uint32());
                            break;
                        case 652:
                            r.leave_conversation_body = $root.im_proto.ConversationLeaveRequestBody.decode(e, e.uint32());
                            break;
                        case 655:
                            r.update_conversation_participant_body = $root.im_proto.UpdateConversationParticipantRequestBody.decode(e, e.uint32());
                            break;
                        case 701:
                            r.delete_message_body = $root.im_proto.DeleteMessageRequestBody.decode(e, e.uint32());
                            break;
                        case 702:
                            r.recall_message_body = $root.im_proto.RecallMessageRequestBody.decode(e, e.uint32());
                            break;
                        case 705:
                            r.modify_message_property_body = $root.im_proto.ModifyMessagePropertyRequestBody.decode(e, e.uint32());
                            break;
                        case 901:
                            r.get_conversation_core_info_body = $root.im_proto.GetConversationCoreInfoRequestBody.decode(e, e.uint32());
                            break;
                        case 902:
                            r.set_conversation_core_info_body = $root.im_proto.SetConversationCoreInfoRequestBody.decode(e, e.uint32());
                            break;
                        case 904:
                            r.upsert_conversation_core_ext_info_body = $root.im_proto.UpsertConversationCoreExtInfoRequestBody.decode(e, e.uint32());
                            break;
                        case 921:
                            r.set_conversation_setting_info_body = $root.im_proto.SetConversationSettingInfoRequestBody.decode(e, e.uint32());
                            break;
                        case 922:
                            r.upsert_conversation_setting_ext_info_body = $root.im_proto.UpsertConversationSettingExtInfoRequestBody.decode(e, e.uint32());
                            break;
                        case 2e3:
                            r.participants_read_index_body = $root.im_proto.GetConversationParticipantsReadIndexV3RequestBody.decode(e, e.uint32());
                            break;
                        case 2001:
                            r.participants_min_index_body = $root.im_proto.GetConversationParticipantsMinIndexV3RequestBody.decode(e, e.uint32());
                            break;
                        case 2005:
                            r.get_ticket_body = $root.im_proto.GetTicketRequestBody.decode(e, e.uint32());
                            break;
                        case 2006:
                            r.get_conversation_list_body = $root.im_proto.GetUserConversationListRequestBody.decode(e, e.uint32());
                            break;
                        case 2010:
                            r.client_ack_body = $root.im_proto.ClientACKRequestBody.decode(e, e.uint32());
                            break;
                        case 2016:
                            r.report_client_metrics_body = $root.im_proto.ReportClientMetricsRequestBody.decode(e, e.uint32());
                            break;
                        case 2017:
                            r.get_configs_body = $root.im_proto.GetConfigsRequestBody.decode(e, e.uint32());
                            break;
                        case 2018:
                            r.unread_count_report_body = $root.im_proto.UnReadCountReportRequestBody.decode(e, e.uint32());
                            break;
                        case 2021:
                            r.modify_message_ext_body = $root.im_proto.ModifyMessageExtRequestBody.decode(e, e.uint32());
                            break;
                        case 2030:
                            r.get_unread_count_body = $root.im_proto.GetUnreadCountRequestBody.decode(e, e.uint32());
                            break;
                        case 2031:
                            r.send_message_p2p_body = $root.im_proto.SendMessageP2PRequestBody.decode(e, e.uint32());
                            break;
                        case 2035:
                            r.get_message_info_by_index_v2_body = $root.im_proto.GetMessageInfoByIndexV2RequestBody.decode(e, e.uint32());
                            break;
                        case 2038:
                            r.batch_get_conversation_participants_readindex = $root.im_proto.BatchGetConversationParticipantsReadIndexRequestBody.decode(e, e.uint32());
                            break;
                        case 2041:
                            r.get_message_info_by_index_v2_range_body = $root.im_proto.GetMessageInfoByIndexV2RangeRequestBody.decode(e, e.uint32());
                            break;
                        case 16001:
                            r.get_open_convs_body = $root.im_proto.GetOpenConvsRequestBody.decode(e, e.uint32());
                            break;
                        case 16002:
                            r.get_messages_by_user_with_open_convs_body = $root.im_proto.GetMessagesByUserWithOpenConvsRequestBody.decode(e, e.uint32());
                            break;
                        case 16003:
                            r.get_user_message_with_open_convs_body = $root.im_proto.GetUserMessageWithOpenConvsRequestBody.decode(e, e.uint32());
                            break;
                        case 17001:
                            r.get_user_conversations_by_tag_body = $root.im_proto.GetUserConversationsByTagRequestBody.decode(e, e.uint32());
                            break;
                        case 17002:
                            r.set_user_all_conversations_settings_body = $root.im_proto.SetUserAllConversationsSettingsRequestBody.decode(e, e.uint32());
                            break;
                        default:
                            e.skipType(7 & o)
                        }
                    }
                    return r
                }
                ,
                e
            }(),
        "SendMessageRequestBody":  function() {
                function e(e) {
                    if (this.ext = {},
                    this.mentioned_users = [],
                    this.client_ext = {},
                    this.security_mentioned_users = [],
                    e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.conversation_id = "",
                e.prototype.conversation_type = 0,
                e.prototype.conversation_short_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.content = "",
                e.prototype.ext = $util.emptyObject,
                e.prototype.message_type = 0,
                e.prototype.ticket = "",
                e.prototype.client_message_id = "",
                e.prototype.mentioned_users = $util.emptyArray,
                e.prototype.ignore_badge_count = !1,
                e.prototype.ref_msg_info = null,
                e.prototype.client_ext = $util.emptyObject,
                e.prototype.unuse_field1 = "",
                e.prototype.sub_conversation_short_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.security_conversation_id = "",
                e.prototype.security_mentioned_users = $util.emptyArray,
                e.prototype.security_to_user_id = "",
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    if (t || (t = $Writer.create()),
                    null != e.conversation_id && Object.hasOwnProperty.call(e, "conversation_id") && t.uint32(10).string(e.conversation_id),
                    null != e.conversation_type && Object.hasOwnProperty.call(e, "conversation_type") && t.uint32(16).int32(e.conversation_type),
                    null != e.conversation_short_id && Object.hasOwnProperty.call(e, "conversation_short_id") && t.uint32(24).int64(e.conversation_short_id),
                    null != e.content && Object.hasOwnProperty.call(e, "content") && t.uint32(34).string(e.content),
                    null != e.ext && Object.hasOwnProperty.call(e, "ext"))
                        for (var n = Object.keys(e.ext), r = 0; r < n.length; ++r)
                            t.uint32(42).fork().uint32(10).string(n[r]).uint32(18).string(e.ext[n[r]]).ldelim();
                    if (null != e.message_type && Object.hasOwnProperty.call(e, "message_type") && t.uint32(48).int32(e.message_type),
                    null != e.ticket && Object.hasOwnProperty.call(e, "ticket") && t.uint32(58).string(e.ticket),
                    null != e.client_message_id && Object.hasOwnProperty.call(e, "client_message_id") && t.uint32(66).string(e.client_message_id),
                    null != e.mentioned_users && e.mentioned_users.length)
                        for (r = 0; r < e.mentioned_users.length; ++r)
                            t.uint32(72).int64(e.mentioned_users[r]);
                    if (null != e.ignore_badge_count && Object.hasOwnProperty.call(e, "ignore_badge_count") && t.uint32(80).bool(e.ignore_badge_count),
                    null != e.ref_msg_info && Object.hasOwnProperty.call(e, "ref_msg_info") && $root.im_proto.ReferencedMessageInfo.encode(e.ref_msg_info, t.uint32(90).fork()).ldelim(),
                    null != e.client_ext && Object.hasOwnProperty.call(e, "client_ext"))
                        for (n = Object.keys(e.client_ext),
                        r = 0; r < n.length; ++r)
                            t.uint32(98).fork().uint32(10).string(n[r]).uint32(18).string(e.client_ext[n[r]]).ldelim();
                    if (null != e.unuse_field1 && Object.hasOwnProperty.call(e, "unuse_field1") && t.uint32(106).string(e.unuse_field1),
                    null != e.sub_conversation_short_id && Object.hasOwnProperty.call(e, "sub_conversation_short_id") && t.uint32(112).int64(e.sub_conversation_short_id),
                    null != e.security_conversation_id && Object.hasOwnProperty.call(e, "security_conversation_id") && t.uint32(402).string(e.security_conversation_id),
                    null != e.security_mentioned_users && e.security_mentioned_users.length)
                        for (r = 0; r < e.security_mentioned_users.length; ++r)
                            t.uint32(410).string(e.security_mentioned_users[r]);
                    return null != e.security_to_user_id && Object.hasOwnProperty.call(e, "security_to_user_id") && t.uint32(418).string(e.security_to_user_id),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n, r, o = void 0 === t ? e.len : e.pos + t, i = new $root.im_proto.SendMessageRequestBody; e.pos < o; ) {
                        var a = e.uint32();
                        switch (a >>> 3) {
                        case 1:
                            i.conversation_id = e.string();
                            break;
                        case 2:
                            i.conversation_type = e.int32();
                            break;
                        case 3:
                            i.conversation_short_id = e.int64();
                            break;
                        case 4:
                            i.content = e.string();
                            break;
                        case 5:
                            i.ext === $util.emptyObject && (i.ext = {});
                            var s = e.uint32() + e.pos;
                            for (n = "",
                            r = ""; e.pos < s; ) {
                                switch ((c = e.uint32()) >>> 3) {
                                case 1:
                                    n = e.string();
                                    break;
                                case 2:
                                    r = e.string();
                                    break;
                                default:
                                    e.skipType(7 & c)
                                }
                            }
                            i.ext[n] = r;
                            break;
                        case 6:
                            i.message_type = e.int32();
                            break;
                        case 7:
                            i.ticket = e.string();
                            break;
                        case 8:
                            i.client_message_id = e.string();
                            break;
                        case 9:
                            if (i.mentioned_users && i.mentioned_users.length || (i.mentioned_users = []),
                            2 == (7 & a))
                                for (s = e.uint32() + e.pos; e.pos < s; )
                                    i.mentioned_users.push(e.int64());
                            else
                                i.mentioned_users.push(e.int64());
                            break;
                        case 10:
                            i.ignore_badge_count = e.bool();
                            break;
                        case 11:
                            i.ref_msg_info = $root.im_proto.ReferencedMessageInfo.decode(e, e.uint32());
                            break;
                        case 12:
                            i.client_ext === $util.emptyObject && (i.client_ext = {});
                            s = e.uint32() + e.pos;
                            for (n = "",
                            r = ""; e.pos < s; ) {
                                var c;
                                switch ((c = e.uint32()) >>> 3) {
                                case 1:
                                    n = e.string();
                                    break;
                                case 2:
                                    r = e.string();
                                    break;
                                default:
                                    e.skipType(7 & c)
                                }
                            }
                            i.client_ext[n] = r;
                            break;
                        case 13:
                            i.unuse_field1 = e.string();
                            break;
                        case 14:
                            i.sub_conversation_short_id = e.int64();
                            break;
                        case 50:
                            i.security_conversation_id = e.string();
                            break;
                        case 51:
                            i.security_mentioned_users && i.security_mentioned_users.length || (i.security_mentioned_users = []),
                            i.security_mentioned_users.push(e.string());
                            break;
                        case 52:
                            i.security_to_user_id = e.string();
                            break;
                        default:
                            e.skipType(7 & a)
                        }
                    }
                    return i
                }
                ,
                e
            }(),
        "TokenInfo": function() {
                function e(e) {
                    if (e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.mark_id = 0,
                e.prototype.type = 0,
                e.prototype.app_id = 0,
                e.prototype.user_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.timestamp = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    return t || (t = $Writer.create()),
                    null != e.mark_id && Object.hasOwnProperty.call(e, "mark_id") && t.uint32(8).int32(e.mark_id),
                    null != e.type && Object.hasOwnProperty.call(e, "type") && t.uint32(16).int32(e.type),
                    null != e.app_id && Object.hasOwnProperty.call(e, "app_id") && t.uint32(24).int32(e.app_id),
                    null != e.user_id && Object.hasOwnProperty.call(e, "user_id") && t.uint32(32).int64(e.user_id),
                    null != e.timestamp && Object.hasOwnProperty.call(e, "timestamp") && t.uint32(40).int64(e.timestamp),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.TokenInfo; e.pos < n; ) {
                        var o = e.uint32();
                        switch (o >>> 3) {
                        case 1:
                            r.mark_id = e.int32();
                            break;
                        case 2:
                            r.type = e.int32();
                            break;
                        case 3:
                            r.app_id = e.int32();
                            break;
                        case 4:
                            r.user_id = e.int64();
                            break;
                        case 5:
                            r.timestamp = e.int64();
                            break;
                        default:
                            e.skipType(7 & o)
                        }
                    }
                    return r
                }
                ,
                e
            }(),
        "MessagesPerUserRequestBody":function() {
                function e(e) {
                    if (e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.cursor = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.limit = 50,
                e.prototype.interval = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.new_user = 0,
                e.prototype.reverse = !1,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    return t || (t = $Writer.create()),
                    null != e.cursor && Object.hasOwnProperty.call(e, "cursor") && t.uint32(8).int64(e.cursor),
                    null != e.limit && Object.hasOwnProperty.call(e, "limit") && t.uint32(16).int32(e.limit),
                    null != e.interval && Object.hasOwnProperty.call(e, "interval") && t.uint32(24).int64(e.interval),
                    null != e.new_user && Object.hasOwnProperty.call(e, "new_user") && t.uint32(32).int32(e.new_user),
                    null != Object.keys(e) && Object.hasOwnProperty.call(e, "reverse") && t.uint32(40).bool(Object.keys(e)),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.MessagesPerUserRequestBody; e.pos < n; ) {
                        var o = e.uint32();
                        switch (o >>> 3) {
                        case 1:
                            r.cursor = e.int64();
                            break;
                        case 2:
                            r.limit = e.int32();
                            break;
                        case 3:
                            r.interval = e.int64();
                            break;
                        case 4:
                            r.new_user = e.int32();
                            break;
                        case 5:
                            r.reverse = e.bool();
                            break;
                        default:
                            e.skipType(7 & o)
                        }
                    }
                    return r
                }
                ,
                e
            }(),
    }
}


function serialize(e) {
            const t = $root.im_proto.Request.encode(e).finish();
            return new Uint8Array(t)
        }

function serializeFrame(e) {
    e.payload = Uint8Array.from(Object.values(e.payload));
    const t = $root.im_proto.Frame.encode(e).finish();
    return new Uint8Array(t)
}

function sendByWs(e, token, pigeon_sign, pigeon_cid, biz_aid){
    const i = {
        "createReq": function (e) {
            return $root.im_proto.Request.create({
                     body: e.body,
                     cmd: e.cmd,
                     sequence_id: $util.Long.fromNumber(e.seqId),
                     refer: 3,
                     token: token,
                     headers: {
                         "pigeon_source": "web",
                         "PIGEON_BIZ_TYPE": "2",
                         "pigeon_sign": pigeon_sign,
                         "session_aid": biz_aid,
                         "session_did": pigeon_cid,
                         "app_name": "im",
                         "priority_region": "cn",
                         "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
                         "cookie_enabled": "true",
                         "browser_language": "zh-CN",
                         "browser_platform": "Win32",
                         "browser_name": "Mozilla",
                         "browser_version": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
                         "browser_online": "true",
                         "screen_width": "1920",
                         "screen_height": "1080",
                         "referer": "",
                         "timezone_name": "Asia/Shanghai"
                     },
                     device_id: pigeon_cid,
                     sdk_version: '1.0.4-beta.2',
                     build_number: '2d97ea6:feat/add_init_callback',
                     inbox_type: 3,
                     device_platform: 'web',
                     // channel: undefined,
                     // device_type: undefined,
                     // os_version: undefined,
                     // version_code: undefined,
                     auth_type: 2
                 })
                }
            }
    let {body: t, cmd: n, inboxType: r, seqId: o} = e
    const s = i.createReq({
                        body: t,
                        cmd: n,
                        inboxType: r,
                        seqId: o
                    })
    const c = serialize(s)
    const l = {
            "pigeon_source": "web",
            "PIGEON_BIZ_TYPE": "2",
            "pigeon_sign": pigeon_sign
        }
    const u= $root.im_proto.Frame.create({
                        service: 10001,
                        method: 1,
                        headers: Object.entries(l).map(([key, value]) => ({
                            key,
                            value
                        })),
                        seqid: $util.Long.fromNumber(o),
                        logid: $util.Long.fromNumber(Date.now()),
                        payload_type: "pb",
                        payload: c
                    });
    return serializeFrame(u)
}

//
// sendByWs({'body': {'send_message_body': {'conversation_id': '2216256679184872:29411390::2:1:pigeon', 'conversation_short_id': {'low': -1262369509, 'high': 1751276475, 'unsigned': false}, 'sub_conversation_short_id': {'low': 2134951207, 'high': 1752460239, 'unsigned': false}, 'conversation_type': 11, 'content': '卖家测试回复', 'mentioned_users': [], 'client_message_id': '0665ba1d-6ad2-4653-8c53-d7aa35d21e1b', 'ticket': '8l755DGsFOr55IWK0WBSH0hXHaBJH9JIxmTboN1ZSoigyZmCnk2TqEt97MYwkjNrSDHpSWM8NdhBtChyvWKwouqcJow41lTPcbzhAwHcyj6rUMbXdzQ3xdn1uWnwwSHY3SlUtPTQia0mIKoaCgLVMuvha9T4m9qjuuir54njwrYJ4l53UzgOPliDvo7fjkNugYx7pfAv7HquSFQ1AYiVYzWSCFqr8uDMtK', 'message_type': 1000, 'ext': {'type': 'text', 'shop_id': '29411390', 'sender_role': '2', 'PIGEON_BIZ_TYPE': '2', 'src': 'pc', 'srcType': '1', 'source': 'pc-web', 'receiver_id': '2216256679184872', 'hierarchical_dimension': '{"dynamic_dimension":"4541_1131_8272_6599_9420_6832_4050_3823_3994_8564_1528_0388_8667_2179_7948_1870_1948_0989_8012_6240_7898_7548_8852_6245_9393_3650_1549_4026_4034_4057_6537_8632_2068_8958_0363_2387_9033_3425_2239_0982_1935_8188_3817_8557_7931_3278_4065_1894_6049_6961_3814_4883_4401_6638_7282_3652_0568_9354_0438_4769_4815_9572_7230_5054_7510_4852_2188_3505_6813_2570_5394_0729","goofy_id":"1.0.1.1625","desk_version":"0.0.0","open_stores":"0","memL":"","cpuL":"","session_throughput":0,"message_throughput_send":0,"message_throughput_revice":0}', 'p:check_Send': '483a6e27-605d-11f0-8269-1c1b0ddd13b6', 'track_info': '{"send_time": "1752461420846", "_send_delta": "394", "_send_delta_2": "475"}', 'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0', 'sender_id': '', 'biz_ext': '{}', 'p:from_source': 'web', 's:mentioned_users': '', 's:client_message_id': '0665ba1d-6ad2-4653-8c53-d7aa35d21e1b'}}}, 'cmd': 100, 'inboxType': 3, 'seqId': 10001}
// , '8kK8DTmT5kKI4LliNaCjn1zUdRyDSn3WtBlsaIwXP1FqQvucFboYAJ', 'MIG6BAxdskASr0RG+bpCV4UEgZeV8bzoxqIL36mgiOehbX9Tq9rOzG8d/YA5pXhO+v/zgn6cQMemQ17YQ6QjZ/hoq80QmKTfHQ4iZ6cPWCNcaav/lvEO0XtHvdkGFq4we268zIOqqPJiMf331HYSamFjRCIe1nkQzBjp6eD5k1k8L54nkO7DZuV8HZy4TlNZQBTPzkV92Xy3IVC9wg5Y3AbEP5Xw05Yw26VgBBCHlaAA0FcOdO9yQ/DIGdf+'
// ,'1469396562216643' , '1383')
