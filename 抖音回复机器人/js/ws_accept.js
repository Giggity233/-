const protobuf = require("protobufjs/minimal");
const $Writer = protobuf.Writer;
const $Reader = protobuf.Reader;
const $util = protobuf.util;




const $root = {
        "im_proto": {
            "ResponseBody": function() {
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
                e.prototype.has_new_message_notify = null,
                e.prototype.has_new_p2p_message_notify = null,
                e.prototype.create_sub_conversation_body = null,
                e.prototype.get_sub_conversation_body = null,
                e.prototype.get_sub_conversation_list_body = null,
                e.prototype.get_conversation_info_v2_body = null,
                e.prototype.create_conversation_v2_body = null,
                e.prototype.get_conversation_info_list_v2_body = null,
                e.prototype.get_conversation_info_list_by_favorite_v2_body = null,
                e.prototype.get_conversation_info_list_by_top_v2_body = null,
                e.prototype.conversation_participants_body = null,
                e.prototype.conversation_add_participants_body = null,
                e.prototype.conversation_remove_participants_body = null,
                e.prototype.update_conversation_participant_body = null,
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
                    null != e.send_message_body && Object.hasOwnProperty.call(e, "send_message_body") && $root.im_proto.SendMessageResponseBody.encode(e.send_message_body, t.uint32(802).fork()).ldelim(),
                    null != e.messages_per_user_body && Object.hasOwnProperty.call(e, "messages_per_user_body") && $root.im_proto.MessagesPerUserResponseBody.encode(e.messages_per_user_body, t.uint32(1602).fork()).ldelim(),
                    null != e.messages_per_user_init_v2_body && Object.hasOwnProperty.call(e, "messages_per_user_init_v2_body") && $root.im_proto.MessagesPerUserInitV2ResponseBody.encode(e.messages_per_user_init_v2_body, t.uint32(1626).fork()).ldelim(),
                    null != e.get_message_by_id_body && Object.hasOwnProperty.call(e, "get_message_by_id_body") && $root.im_proto.GetMessageByIdResponseBody.encode(e.get_message_by_id_body, t.uint32(1690).fork()).ldelim(),
                    null != e.messages_in_conversation_body && Object.hasOwnProperty.call(e, "messages_in_conversation_body") && $root.im_proto.MessagesInConversationResponseBody.encode(e.messages_in_conversation_body, t.uint32(2410).fork()).ldelim(),
                    null != e.send_user_action_body && Object.hasOwnProperty.call(e, "send_user_action_body") && $root.im_proto.SendUserActionResponseBody.encode(e.send_user_action_body, t.uint32(3282).fork()).ldelim(),
                    null != e.has_new_message_notify && Object.hasOwnProperty.call(e, "has_new_message_notify") && $root.im_proto.NewMessageNotify.encode(e.has_new_message_notify, t.uint32(4002).fork()).ldelim(),
                    null != e.has_new_p2p_message_notify && Object.hasOwnProperty.call(e, "has_new_p2p_message_notify") && $root.im_proto.NewP2PMessageNotify.encode(e.has_new_p2p_message_notify, t.uint32(4034).fork()).ldelim(),
                    null != e.conversation_participants_body && Object.hasOwnProperty.call(e, "conversation_participants_body") && $root.im_proto.ConversationParticipantsListResponseBody.encode(e.conversation_participants_body, t.uint32(4842).fork()).ldelim(),
                    null != e.get_conversation_info_v2_body && Object.hasOwnProperty.call(e, "get_conversation_info_v2_body") && $root.im_proto.GetConversationInfoV2ResponseBody.encode(e.get_conversation_info_v2_body, t.uint32(4866).fork()).ldelim(),
                    null != e.create_conversation_v2_body && Object.hasOwnProperty.call(e, "create_conversation_v2_body") && $root.im_proto.CreateConversationV2ResponseBody.encode(e.create_conversation_v2_body, t.uint32(4874).fork()).ldelim(),
                    null != e.get_conversation_info_list_v2_body && Object.hasOwnProperty.call(e, "get_conversation_info_list_v2_body") && $root.im_proto.GetConversationInfoListV2ResponseBody.encode(e.get_conversation_info_list_v2_body, t.uint32(4882).fork()).ldelim(),
                    null != e.get_conversation_info_list_by_favorite_v2_body && Object.hasOwnProperty.call(e, "get_conversation_info_list_by_favorite_v2_body") && $root.im_proto.GetConversationInfoListByFavoriteV2ResponseBody.encode(e.get_conversation_info_list_by_favorite_v2_body, t.uint32(4890).fork()).ldelim(),
                    null != e.get_conversation_info_list_by_top_v2_body && Object.hasOwnProperty.call(e, "get_conversation_info_list_by_top_v2_body") && $root.im_proto.GetConversationInfoListByTopV2ResponseBody.encode(e.get_conversation_info_list_by_top_v2_body, t.uint32(4898).fork()).ldelim(),
                    null != e.create_sub_conversation_body && Object.hasOwnProperty.call(e, "create_sub_conversation_body") && $root.im_proto.CreateSubConversationResponseBody.encode(e.create_sub_conversation_body, t.uint32(4930).fork()).ldelim(),
                    null != e.get_sub_conversation_body && Object.hasOwnProperty.call(e, "get_sub_conversation_body") && $root.im_proto.GetSubConversationResponseBody.encode(e.get_sub_conversation_body, t.uint32(4938).fork()).ldelim(),
                    null != e.get_sub_conversation_list_body && Object.hasOwnProperty.call(e, "get_sub_conversation_list_body") && $root.im_proto.GetSubConversationListResponseBody.encode(e.get_sub_conversation_list_body, t.uint32(4946).fork()).ldelim(),
                    null != e.conversation_add_participants_body && Object.hasOwnProperty.call(e, "conversation_add_participants_body") && $root.im_proto.ConversationAddParticipantsResponseBody.encode(e.conversation_add_participants_body, t.uint32(5202).fork()).ldelim(),
                    null != e.conversation_remove_participants_body && Object.hasOwnProperty.call(e, "conversation_remove_participants_body") && $root.im_proto.ConversationRemoveParticipantsResponseBody.encode(e.conversation_remove_participants_body, t.uint32(5210).fork()).ldelim(),
                    null != e.update_conversation_participant_body && Object.hasOwnProperty.call(e, "update_conversation_participant_body") && $root.im_proto.UpdateConversationParticipantResponseBody.encode(e.update_conversation_participant_body, t.uint32(5242).fork()).ldelim(),
                    null != e.recall_message_body && Object.hasOwnProperty.call(e, "recall_message_body") && $root.im_proto.RecallMessageResponseBody.encode(e.recall_message_body, t.uint32(5618).fork()).ldelim(),
                    null != e.modify_message_property_body && Object.hasOwnProperty.call(e, "modify_message_property_body") && $root.im_proto.ModifyMessagePropertyResponseBody.encode(e.modify_message_property_body, t.uint32(5642).fork()).ldelim(),
                    null != e.get_conversation_core_info_body && Object.hasOwnProperty.call(e, "get_conversation_core_info_body") && $root.im_proto.GetConversationCoreInfoResponseBody.encode(e.get_conversation_core_info_body, t.uint32(7210).fork()).ldelim(),
                    null != e.set_conversation_core_info_body && Object.hasOwnProperty.call(e, "set_conversation_core_info_body") && $root.im_proto.SetConversationCoreInfoResponseBody.encode(e.set_conversation_core_info_body, t.uint32(7218).fork()).ldelim(),
                    null != e.upsert_conversation_core_ext_info_body && Object.hasOwnProperty.call(e, "upsert_conversation_core_ext_info_body") && $root.im_proto.UpsertConversationCoreExtInfoResponseBody.encode(e.upsert_conversation_core_ext_info_body, t.uint32(7234).fork()).ldelim(),
                    null != e.set_conversation_setting_info_body && Object.hasOwnProperty.call(e, "set_conversation_setting_info_body") && $root.im_proto.SetConversationSettingInfoResponseBody.encode(e.set_conversation_setting_info_body, t.uint32(7370).fork()).ldelim(),
                    null != e.upsert_conversation_setting_ext_info_body && Object.hasOwnProperty.call(e, "upsert_conversation_setting_ext_info_body") && $root.im_proto.UpsertConversationSettingExtInfoResponseBody.encode(e.upsert_conversation_setting_ext_info_body, t.uint32(7378).fork()).ldelim(),
                    null != e.participants_read_index_body && Object.hasOwnProperty.call(e, "participants_read_index_body") && $root.im_proto.GetConversationParticipantsReadIndexV3ResponseBody.encode(e.participants_read_index_body, t.uint32(16002).fork()).ldelim(),
                    null != e.participants_min_index_body && Object.hasOwnProperty.call(e, "participants_min_index_body") && $root.im_proto.GetConversationParticipantsMinIndexV3ResponseBody.encode(e.participants_min_index_body, t.uint32(16010).fork()).ldelim(),
                    null != e.get_ticket_body && Object.hasOwnProperty.call(e, "get_ticket_body") && $root.im_proto.GetTicketResponseBody.encode(e.get_ticket_body, t.uint32(16042).fork()).ldelim(),
                    null != e.get_conversation_list_body && Object.hasOwnProperty.call(e, "get_conversation_list_body") && $root.im_proto.GetUserConversationListResponseBody.encode(e.get_conversation_list_body, t.uint32(16050).fork()).ldelim(),
                    null != e.client_ack_body && Object.hasOwnProperty.call(e, "client_ack_body") && $root.im_proto.ClientACKResponseBody.encode(e.client_ack_body, t.uint32(16082).fork()).ldelim(),
                    null != e.report_client_metrics_body && Object.hasOwnProperty.call(e, "report_client_metrics_body") && $root.im_proto.ReportClientMetricsResponseBody.encode(e.report_client_metrics_body, t.uint32(16130).fork()).ldelim(),
                    null != e.get_configs_body && Object.hasOwnProperty.call(e, "get_configs_body") && $root.im_proto.GetConfigsResponseBody.encode(e.get_configs_body, t.uint32(16138).fork()).ldelim(),
                    null != e.unread_count_report_body && Object.hasOwnProperty.call(e, "unread_count_report_body") && $root.im_proto.UnReadCountReportResponseBody.encode(e.unread_count_report_body, t.uint32(16146).fork()).ldelim(),
                    null != e.modify_message_ext_body && Object.hasOwnProperty.call(e, "modify_message_ext_body") && $root.im_proto.ModifyMessageExtResponseBody.encode(e.modify_message_ext_body, t.uint32(16170).fork()).ldelim(),
                    null != e.get_unread_count_body && Object.hasOwnProperty.call(e, "get_unread_count_body") && $root.im_proto.GetUnreadCountResponseBody.encode(e.get_unread_count_body, t.uint32(16242).fork()).ldelim(),
                    null != e.send_message_p2p_body && Object.hasOwnProperty.call(e, "send_message_p2p_body") && $root.im_proto.SendMessageP2PResponseBody.encode(e.send_message_p2p_body, t.uint32(16250).fork()).ldelim(),
                    null != e.get_message_info_by_index_v2_body && Object.hasOwnProperty.call(e, "get_message_info_by_index_v2_body") && $root.im_proto.GetMessageInfoByIndexV2ResponseBody.encode(e.get_message_info_by_index_v2_body, t.uint32(16282).fork()).ldelim(),
                    null != e.get_message_info_by_index_v2_range_body && Object.hasOwnProperty.call(e, "get_message_info_by_index_v2_range_body") && $root.im_proto.GetMessageInfoByIndexV2RangeResponseBody.encode(e.get_message_info_by_index_v2_range_body, t.uint32(16330).fork()).ldelim(),
                    null != e.get_open_convs_body && Object.hasOwnProperty.call(e, "get_open_convs_body") && $root.im_proto.GetOpenConvsResponseBody.encode(e.get_open_convs_body, t.uint32(128010).fork()).ldelim(),
                    null != e.get_messages_by_user_with_open_convs_body && Object.hasOwnProperty.call(e, "get_messages_by_user_with_open_convs_body") && $root.im_proto.GetMessagesByUserWithOpenConvsResponseBody.encode(e.get_messages_by_user_with_open_convs_body, t.uint32(128018).fork()).ldelim(),
                    null != e.get_user_message_with_open_convs_body && Object.hasOwnProperty.call(e, "get_user_message_with_open_convs_body") && $root.im_proto.GetUserMessageWithOpenConvsResponseBody.encode(e.get_user_message_with_open_convs_body, t.uint32(128026).fork()).ldelim(),
                    null != e.get_user_conversations_by_tag_body && Object.hasOwnProperty.call(e, "get_user_conversations_by_tag_body") && $root.im_proto.GetUserConversationsByTagResponseBody.encode(e.get_user_conversations_by_tag_body, t.uint32(136010).fork()).ldelim(),
                    null != e.set_user_all_conversations_settings_body && Object.hasOwnProperty.call(e, "set_user_all_conversations_settings_body") && $root.im_proto.SetUserAllConversationsSettingsResponseBody.encode(e.set_user_all_conversations_settings_body, t.uint32(136018).fork()).ldelim(),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.ResponseBody; e.pos < n; ) {
                        var o = e.uint32();
                        switch (o >>> 3) {
                        case 100:
                            r.send_message_body = $root.im_proto.SendMessageResponseBody.decode(e, e.uint32());
                            break;
                        case 200:
                            r.messages_per_user_body = $root.im_proto.MessagesPerUserResponseBody.decode(e, e.uint32());
                            break;
                        case 203:
                            r.messages_per_user_init_v2_body = $root.im_proto.MessagesPerUserInitV2ResponseBody.decode(e, e.uint32());
                            break;
                        case 211:
                            r.get_message_by_id_body = $root.im_proto.GetMessageByIdResponseBody.decode(e, e.uint32());
                            break;
                        case 301:
                            r.messages_in_conversation_body = $root.im_proto.MessagesInConversationResponseBody.decode(e, e.uint32());
                            break;
                        case 410:
                            r.send_user_action_body = $root.im_proto.SendUserActionResponseBody.decode(e, e.uint32());
                            break;
                        case 500:
                            r.has_new_message_notify = $root.im_proto.NewMessageNotify.decode(e, e.uint32());
                            break;
                        case 504:
                            r.has_new_p2p_message_notify = $root.im_proto.NewP2PMessageNotify.decode(e, e.uint32());
                            break;
                        case 616:
                            r.create_sub_conversation_body = $root.im_proto.CreateSubConversationResponseBody.decode(e, e.uint32());
                            break;
                        case 617:
                            r.get_sub_conversation_body = $root.im_proto.GetSubConversationResponseBody.decode(e, e.uint32());
                            break;
                        case 618:
                            r.get_sub_conversation_list_body = $root.im_proto.GetSubConversationListResponseBody.decode(e, e.uint32());
                            break;
                        case 608:
                            r.get_conversation_info_v2_body = $root.im_proto.GetConversationInfoV2ResponseBody.decode(e, e.uint32());
                            break;
                        case 609:
                            r.create_conversation_v2_body = $root.im_proto.CreateConversationV2ResponseBody.decode(e, e.uint32());
                            break;
                        case 610:
                            r.get_conversation_info_list_v2_body = $root.im_proto.GetConversationInfoListV2ResponseBody.decode(e, e.uint32());
                            break;
                        case 611:
                            r.get_conversation_info_list_by_favorite_v2_body = $root.im_proto.GetConversationInfoListByFavoriteV2ResponseBody.decode(e, e.uint32());
                            break;
                        case 612:
                            r.get_conversation_info_list_by_top_v2_body = $root.im_proto.GetConversationInfoListByTopV2ResponseBody.decode(e, e.uint32());
                            break;
                        case 605:
                            r.conversation_participants_body = $root.im_proto.ConversationParticipantsListResponseBody.decode(e, e.uint32());
                            break;
                        case 650:
                            r.conversation_add_participants_body = $root.im_proto.ConversationAddParticipantsResponseBody.decode(e, e.uint32());
                            break;
                        case 651:
                            r.conversation_remove_participants_body = $root.im_proto.ConversationRemoveParticipantsResponseBody.decode(e, e.uint32());
                            break;
                        case 655:
                            r.update_conversation_participant_body = $root.im_proto.UpdateConversationParticipantResponseBody.decode(e, e.uint32());
                            break;
                        case 702:
                            r.recall_message_body = $root.im_proto.RecallMessageResponseBody.decode(e, e.uint32());
                            break;
                        case 705:
                            r.modify_message_property_body = $root.im_proto.ModifyMessagePropertyResponseBody.decode(e, e.uint32());
                            break;
                        case 901:
                            r.get_conversation_core_info_body = $root.im_proto.GetConversationCoreInfoResponseBody.decode(e, e.uint32());
                            break;
                        case 902:
                            r.set_conversation_core_info_body = $root.im_proto.SetConversationCoreInfoResponseBody.decode(e, e.uint32());
                            break;
                        case 904:
                            r.upsert_conversation_core_ext_info_body = $root.im_proto.UpsertConversationCoreExtInfoResponseBody.decode(e, e.uint32());
                            break;
                        case 921:
                            r.set_conversation_setting_info_body = $root.im_proto.SetConversationSettingInfoResponseBody.decode(e, e.uint32());
                            break;
                        case 922:
                            r.upsert_conversation_setting_ext_info_body = $root.im_proto.UpsertConversationSettingExtInfoResponseBody.decode(e, e.uint32());
                            break;
                        case 2e3:
                            r.participants_read_index_body = $root.im_proto.GetConversationParticipantsReadIndexV3ResponseBody.decode(e, e.uint32());
                            break;
                        case 2001:
                            r.participants_min_index_body = $root.im_proto.GetConversationParticipantsMinIndexV3ResponseBody.decode(e, e.uint32());
                            break;
                        case 2005:
                            r.get_ticket_body = $root.im_proto.GetTicketResponseBody.decode(e, e.uint32());
                            break;
                        case 2006:
                            r.get_conversation_list_body = $root.im_proto.GetUserConversationListResponseBody.decode(e, e.uint32());
                            break;
                        case 2010:
                            r.client_ack_body = $root.im_proto.ClientACKResponseBody.decode(e, e.uint32());
                            break;
                        case 2016:
                            r.report_client_metrics_body = $root.im_proto.ReportClientMetricsResponseBody.decode(e, e.uint32());
                            break;
                        case 2017:
                            r.get_configs_body = $root.im_proto.GetConfigsResponseBody.decode(e, e.uint32());
                            break;
                        case 2018:
                            r.unread_count_report_body = $root.im_proto.UnReadCountReportResponseBody.decode(e, e.uint32());
                            break;
                        case 2021:
                            r.modify_message_ext_body = $root.im_proto.ModifyMessageExtResponseBody.decode(e, e.uint32());
                            break;
                        case 2030:
                            r.get_unread_count_body = $root.im_proto.GetUnreadCountResponseBody.decode(e, e.uint32());
                            break;
                        case 2031:
                            r.send_message_p2p_body = $root.im_proto.SendMessageP2PResponseBody.decode(e, e.uint32());
                            break;
                        case 2035:
                            r.get_message_info_by_index_v2_body = $root.im_proto.GetMessageInfoByIndexV2ResponseBody.decode(e, e.uint32());
                            break;
                        case 2041:
                            r.get_message_info_by_index_v2_range_body = $root.im_proto.GetMessageInfoByIndexV2RangeResponseBody.decode(e, e.uint32());
                            break;
                        case 16001:
                            r.get_open_convs_body = $root.im_proto.GetOpenConvsResponseBody.decode(e, e.uint32());
                            break;
                        case 16002:
                            r.get_messages_by_user_with_open_convs_body = $root.im_proto.GetMessagesByUserWithOpenConvsResponseBody.decode(e, e.uint32());
                            break;
                        case 16003:
                            r.get_user_message_with_open_convs_body = $root.im_proto.GetUserMessageWithOpenConvsResponseBody.decode(e, e.uint32());
                            break;
                        case 17001:
                            r.get_user_conversations_by_tag_body = $root.im_proto.GetUserConversationsByTagResponseBody.decode(e, e.uint32());
                            break;
                        case 17002:
                            r.set_user_all_conversations_settings_body = $root.im_proto.SetUserAllConversationsSettingsResponseBody.decode(e, e.uint32());
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
            "SendMessageResponseBody": function() {
                function e(e) {
                    if (e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.server_message_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.extra_info = "",
                e.prototype.status = 0,
                e.prototype.client_message_id = "",
                e.prototype.check_code = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.check_message = "",
                e.prototype.filtered_content = "",
                e.prototype.is_async_send = !1,
                e.prototype.new_ticket = "",
                e.prototype.conversation = null,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    return t || (t = $Writer.create()),
                    null != e.server_message_id && Object.hasOwnProperty.call(e, "server_message_id") && t.uint32(8).int64(e.server_message_id),
                    null != e.extra_info && Object.hasOwnProperty.call(e, "extra_info") && t.uint32(18).string(e.extra_info),
                    null != e.status && Object.hasOwnProperty.call(e, "status") && t.uint32(24).int32(e.status),
                    null != e.client_message_id && Object.hasOwnProperty.call(e, "client_message_id") && t.uint32(34).string(e.client_message_id),
                    null != e.check_code && Object.hasOwnProperty.call(e, "check_code") && t.uint32(40).int64(e.check_code),
                    null != e.check_message && Object.hasOwnProperty.call(e, "check_message") && t.uint32(50).string(e.check_message),
                    null != e.filtered_content && Object.hasOwnProperty.call(e, "filtered_content") && t.uint32(58).string(e.filtered_content),
                    null != e.is_async_send && Object.hasOwnProperty.call(e, "is_async_send") && t.uint32(64).bool(e.is_async_send),
                    null != e.new_ticket && Object.hasOwnProperty.call(e, "new_ticket") && t.uint32(74).string(e.new_ticket),
                    null != e.conversation && Object.hasOwnProperty.call(e, "conversation") && $root.im_proto.ConversationInfoV2.encode(e.conversation, t.uint32(82).fork()).ldelim(),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.SendMessageResponseBody; e.pos < n; ) {
                        var o = e.uint32();
                        switch (o >>> 3) {
                        case 1:
                            r.server_message_id = e.int64();
                            break;
                        case 2:
                            r.extra_info = e.string();
                            break;
                        case 3:
                            r.status = e.int32();
                            break;
                        case 4:
                            r.client_message_id = e.string();
                            break;
                        case 5:
                            r.check_code = e.int64();
                            break;
                        case 6:
                            r.check_message = e.string();
                            break;
                        case 7:
                            r.filtered_content = e.string();
                            break;
                        case 8:
                            r.is_async_send = e.bool();
                            break;
                        case 9:
                            r.new_ticket = e.string();
                            break;
                        case 10:
                            r.conversation = $root.im_proto.ConversationInfoV2.decode(e, e.uint32());
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
            "MessagesPerUserResponseBody": function() {
                function e(e) {
                    if (this.messages = [],
                    this.conversation_badge_count = [],
                    this.hasmore_message_conv_list = [],
                    e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.messages = $util.emptyArray,
                e.prototype.next_cursor = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.has_more = !1,
                e.prototype.next_interval = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.next_conversation_version = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.conversation_badge_count = $util.emptyArray,
                e.prototype.next_cmd_index = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.hasmore_message_conv_list = $util.emptyArray,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    if (t || (t = $Writer.create()),
                    null != e.messages && e.messages.length)
                        for (var n = 0; n < e.messages.length; ++n)
                            $root.im_proto.MessageBody.encode(e.messages[n], t.uint32(10).fork()).ldelim();
                    if (null != e.next_cursor && Object.hasOwnProperty.call(e, "next_cursor") && t.uint32(16).int64(e.next_cursor),
                    null != e.has_more && Object.hasOwnProperty.call(e, "has_more") && t.uint32(24).bool(e.has_more),
                    null != e.next_interval && Object.hasOwnProperty.call(e, "next_interval") && t.uint32(32).int64(e.next_interval),
                    null != e.next_conversation_version && Object.hasOwnProperty.call(e, "next_conversation_version") && t.uint32(40).int64(e.next_conversation_version),
                    null != e.conversation_badge_count && e.conversation_badge_count.length)
                        for (n = 0; n < e.conversation_badge_count.length; ++n)
                            $root.im_proto.ConversationBadgeCountInfo.encode(e.conversation_badge_count[n], t.uint32(50).fork()).ldelim();
                    if (null != e.next_cmd_index && Object.hasOwnProperty.call(e, "next_cmd_index") && t.uint32(56).int64(e.next_cmd_index),
                    null != e.hasmore_message_conv_list && e.hasmore_message_conv_list.length)
                        for (n = 0; n < e.hasmore_message_conv_list.length; ++n)
                            t.uint32(64).int64(e.hasmore_message_conv_list[n]);
                    return t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.MessagesPerUserResponseBody; e.pos < n; ) {
                        var o = e.uint32();
                        switch (o >>> 3) {
                        case 1:
                            r.messages && r.messages.length || (r.messages = []),
                            r.messages.push($root.im_proto.MessageBody.decode(e, e.uint32()));
                            break;
                        case 2:
                            r.next_cursor = e.int64();
                            break;
                        case 3:
                            r.has_more = e.bool();
                            break;
                        case 4:
                            r.next_interval = e.int64();
                            break;
                        case 5:
                            r.next_conversation_version = e.int64();
                            break;
                        case 6:
                            r.conversation_badge_count && r.conversation_badge_count.length || (r.conversation_badge_count = []),
                            r.conversation_badge_count.push($root.im_proto.ConversationBadgeCountInfo.decode(e, e.uint32()));
                            break;
                        case 7:
                            r.next_cmd_index = e.int64();
                            break;
                        case 8:
                            if (r.hasmore_message_conv_list && r.hasmore_message_conv_list.length || (r.hasmore_message_conv_list = []),
                            2 == (7 & o))
                                for (var i = e.uint32() + e.pos; e.pos < i; )
                                    r.hasmore_message_conv_list.push(e.int64());
                            else
                                r.hasmore_message_conv_list.push(e.int64());
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
            "NewMessageNotify":function() {
                function e(e) {
                    if (e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.conversation_id = "",
                e.prototype.conversation_type = 0,
                e.prototype.notify_type = 1,
                e.prototype.message = null,
                e.prototype.previous_cursor = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.next_cursor = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.index_in_conversation = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.index_in_conversation_v2 = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.conversation_version = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.previous_conversation_version = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.cmd_message_index = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.badge_count = 0,
                e.prototype.trace = null,
                e.prototype.ref_msg_info = null,
                e.prototype.previous_msg_index_in_conv = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.readconv_version = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.pre_readconv_version = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.mute_badge_count_info = null,
                e.prototype.sub_conversation_short_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    return t || (t = $Writer.create()),
                    null != e.conversation_id && Object.hasOwnProperty.call(e, "conversation_id") && t.uint32(18).string(e.conversation_id),
                    null != e.conversation_type && Object.hasOwnProperty.call(e, "conversation_type") && t.uint32(24).int32(e.conversation_type),
                    null != e.notify_type && Object.hasOwnProperty.call(e, "notify_type") && t.uint32(32).int32(e.notify_type),
                    null != e.message && Object.hasOwnProperty.call(e, "message") && $root.im_proto.MessageBody.encode(e.message, t.uint32(42).fork()).ldelim(),
                    null != e.previous_cursor && Object.hasOwnProperty.call(e, "previous_cursor") && t.uint32(48).int64(e.previous_cursor),
                    null != e.next_cursor && Object.hasOwnProperty.call(e, "next_cursor") && t.uint32(56).int64(e.next_cursor),
                    null != e.index_in_conversation && Object.hasOwnProperty.call(e, "index_in_conversation") && t.uint32(64).int64(e.index_in_conversation),
                    null != e.index_in_conversation_v2 && Object.hasOwnProperty.call(e, "index_in_conversation_v2") && t.uint32(72).int64(e.index_in_conversation_v2),
                    null != e.conversation_version && Object.hasOwnProperty.call(e, "conversation_version") && t.uint32(80).int64(e.conversation_version),
                    null != e.previous_conversation_version && Object.hasOwnProperty.call(e, "previous_conversation_version") && t.uint32(88).int64(e.previous_conversation_version),
                    null != e.cmd_message_index && Object.hasOwnProperty.call(e, "cmd_message_index") && t.uint32(96).int64(e.cmd_message_index),
                    null != e.badge_count && Object.hasOwnProperty.call(e, "badge_count") && t.uint32(104).int32(e.badge_count),
                    null != e.trace && Object.hasOwnProperty.call(e, "trace") && $root.im_proto.MsgTrace.encode(e.trace, t.uint32(114).fork()).ldelim(),
                    null != e.ref_msg_info && Object.hasOwnProperty.call(e, "ref_msg_info") && $root.im_proto.ReferenceInfo.encode(e.ref_msg_info, t.uint32(122).fork()).ldelim(),
                    null != e.previous_msg_index_in_conv && Object.hasOwnProperty.call(e, "previous_msg_index_in_conv") && t.uint32(128).int64(e.previous_msg_index_in_conv),
                    null != e.readconv_version && Object.hasOwnProperty.call(e, "readconv_version") && t.uint32(136).int64(e.readconv_version),
                    null != e.pre_readconv_version && Object.hasOwnProperty.call(e, "pre_readconv_version") && t.uint32(144).int64(e.pre_readconv_version),
                    null != e.mute_badge_count_info && Object.hasOwnProperty.call(e, "mute_badge_count_info") && $root.im_proto.MuteBadgeCountInfo.encode(e.mute_badge_count_info, t.uint32(154).fork()).ldelim(),
                    null != e.sub_conversation_short_id && Object.hasOwnProperty.call(e, "sub_conversation_short_id") && t.uint32(160).int64(e.sub_conversation_short_id),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.NewMessageNotify; e.pos < n; ) {
                        var o = e.uint32();
                        switch (o >>> 3) {
                        case 2:
                            r.conversation_id = e.string();
                            break;
                        case 3:
                            r.conversation_type = e.int32();
                            break;
                        case 4:
                            r.notify_type = e.int32();
                            break;
                        case 5:
                            r.message = $root.im_proto.MessageBody.decode(e, e.uint32());
                            break;
                        case 6:
                            r.previous_cursor = e.int64();
                            break;
                        case 7:
                            r.next_cursor = e.int64();
                            break;
                        case 8:
                            r.index_in_conversation = e.int64();
                            break;
                        case 9:
                            r.index_in_conversation_v2 = e.int64();
                            break;
                        case 10:
                            r.conversation_version = e.int64();
                            break;
                        case 11:
                            r.previous_conversation_version = e.int64();
                            break;
                        case 12:
                            r.cmd_message_index = e.int64();
                            break;
                        case 13:
                            r.badge_count = e.int32();
                            break;
                        case 14:
                            r.trace = $root.im_proto.MsgTrace.decode(e, e.uint32());
                            break;
                        case 15:
                            r.ref_msg_info = $root.im_proto.ReferenceInfo.decode(e, e.uint32());
                            break;
                        case 16:
                            r.previous_msg_index_in_conv = e.int64();
                            break;
                        case 17:
                            r.readconv_version = e.int64();
                            break;
                        case 18:
                            r.pre_readconv_version = e.int64();
                            break;
                        case 19:
                            r.mute_badge_count_info = $root.im_proto.MuteBadgeCountInfo.decode(e, e.uint32());
                            break;
                        case 20:
                            r.sub_conversation_short_id = e.int64();
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
            "MessageBody":function() {
                function e(e) {
                    if (this.ext = {},
                    this.property_list = {},
                    this.user_profile = {},
                    e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.conversation_id = "",
                e.prototype.conversation_type = 0,
                e.prototype.server_message_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.index_in_conversation = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.conversation_short_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.message_type = 0,
                e.prototype.sender = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.content = "",
                e.prototype.ext = $util.emptyObject,
                e.prototype.create_time = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.version = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.status = 0,
                e.prototype.order_in_conversation = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.sec_sender = "",
                e.prototype.property_list = $util.emptyObject,
                e.prototype.user_profile = $util.emptyObject,
                e.prototype.index_in_conversation_v2 = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.reference_info = null,
                e.prototype.index_in_conversation_v1 = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.sub_conversation_short_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    if (t || (t = $Writer.create()),
                    null != e.conversation_id && Object.hasOwnProperty.call(e, "conversation_id") && t.uint32(10).string(e.conversation_id),
                    null != e.conversation_type && Object.hasOwnProperty.call(e, "conversation_type") && t.uint32(16).int32(e.conversation_type),
                    null != e.server_message_id && Object.hasOwnProperty.call(e, "server_message_id") && t.uint32(24).int64(e.server_message_id),
                    null != e.index_in_conversation && Object.hasOwnProperty.call(e, "index_in_conversation") && t.uint32(32).int64(e.index_in_conversation),
                    null != e.conversation_short_id && Object.hasOwnProperty.call(e, "conversation_short_id") && t.uint32(40).int64(e.conversation_short_id),
                    null != e.message_type && Object.hasOwnProperty.call(e, "message_type") && t.uint32(48).int32(e.message_type),
                    null != e.sender && Object.hasOwnProperty.call(e, "sender") && t.uint32(56).int64(e.sender),
                    null != e.content && Object.hasOwnProperty.call(e, "content") && t.uint32(66).string(e.content),
                    null != e.ext && Object.hasOwnProperty.call(e, "ext"))
                        for (var n = Object.keys(e.ext), r = 0; r < n.length; ++r)
                            t.uint32(74).fork().uint32(10).string(n[r]).uint32(18).string(e.ext[n[r]]).ldelim();
                    if (null != e.create_time && Object.hasOwnProperty.call(e, "create_time") && t.uint32(80).int64(e.create_time),
                    null != e.version && Object.hasOwnProperty.call(e, "version") && t.uint32(88).int64(e.version),
                    null != e.status && Object.hasOwnProperty.call(e, "status") && t.uint32(96).int32(e.status),
                    null != e.order_in_conversation && Object.hasOwnProperty.call(e, "order_in_conversation") && t.uint32(104).int64(e.order_in_conversation),
                    null != e.sec_sender && Object.hasOwnProperty.call(e, "sec_sender") && t.uint32(114).string(e.sec_sender),
                    null != e.property_list && Object.hasOwnProperty.call(e, "property_list"))
                        for (n = Object.keys(e.property_list),
                        r = 0; r < n.length; ++r)
                            t.uint32(122).fork().uint32(10).string(n[r]),
                            $root.im_proto.PropertyItemList.encode(e.property_list[n[r]], t.uint32(18).fork()).ldelim().ldelim();
                    if (null != e.user_profile && Object.hasOwnProperty.call(e, "user_profile"))
                        for (n = Object.keys(e.user_profile),
                        r = 0; r < n.length; ++r)
                            t.uint32(130).fork().uint32(10).string(n[r]).uint32(18).string(e.user_profile[n[r]]).ldelim();
                    return null != e.index_in_conversation_v2 && Object.hasOwnProperty.call(e, "index_in_conversation_v2") && t.uint32(136).int64(e.index_in_conversation_v2),
                    null != e.reference_info && Object.hasOwnProperty.call(e, "reference_info") && $root.im_proto.ReferenceInfo.encode(e.reference_info, t.uint32(146).fork()).ldelim(),
                    null != e.index_in_conversation_v1 && Object.hasOwnProperty.call(e, "index_in_conversation_v1") && t.uint32(152).int64(e.index_in_conversation_v1),
                    null != e.sub_conversation_short_id && Object.hasOwnProperty.call(e, "sub_conversation_short_id") && t.uint32(160).int64(e.sub_conversation_short_id),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n, r, o = void 0 === t ? e.len : e.pos + t, i = new $root.im_proto.MessageBody; e.pos < o; ) {
                        var a = e.uint32();
                        switch (a >>> 3) {
                        case 1:
                            i.conversation_id = e.string();
                            break;
                        case 2:
                            i.conversation_type = e.int32();
                            break;
                        case 3:
                            i.server_message_id = e.int64();
                            break;
                        case 4:
                            i.index_in_conversation = e.int64();
                            break;
                        case 5:
                            i.conversation_short_id = e.int64();
                            break;
                        case 6:
                            i.message_type = e.int32();
                            break;
                        case 7:
                            i.sender = e.int64();
                            break;
                        case 8:
                            i.content = e.string();
                            break;
                        case 9:
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
                        case 10:
                            i.create_time = e.int64();
                            break;
                        case 11:
                            i.version = e.int64();
                            break;
                        case 12:
                            i.status = e.int32();
                            break;
                        case 13:
                            i.order_in_conversation = e.int64();
                            break;
                        case 14:
                            i.sec_sender = e.string();
                            break;
                        case 15:
                            i.property_list === $util.emptyObject && (i.property_list = {});
                            s = e.uint32() + e.pos;
                            for (n = "",
                            r = null; e.pos < s; ) {
                                switch ((c = e.uint32()) >>> 3) {
                                case 1:
                                    n = e.string();
                                    break;
                                case 2:
                                    r = $root.im_proto.PropertyItemList.decode(e, e.uint32());
                                    break;
                                default:
                                    e.skipType(7 & c)
                                }
                            }
                            i.property_list[n] = r;
                            break;
                        case 16:
                            i.user_profile === $util.emptyObject && (i.user_profile = {});
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
                            i.user_profile[n] = r;
                            break;
                        case 17:
                            i.index_in_conversation_v2 = e.int64();
                            break;
                        case 18:
                            i.reference_info = $root.im_proto.ReferenceInfo.decode(e, e.uint32());
                            break;
                        case 19:
                            i.index_in_conversation_v1 = e.int64();
                            break;
                        case 20:
                            i.sub_conversation_short_id = e.int64();
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
            "MsgTrace": function() {
                function e(e) {
                    if (this.metrics = {},
                    e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.metrics = $util.emptyObject,
                e.prototype.path = 0,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    if (t || (t = $Writer.create()),
                    null != e.metrics && Object.hasOwnProperty.call(e, "metrics"))
                        for (var n = Object.keys(e.metrics), r = 0; r < n.length; ++r)
                            t.uint32(10).fork().uint32(8).int32(n[r]).uint32(16).int64(e.metrics[n[r]]).ldelim();
                    return null != e.path && Object.hasOwnProperty.call(e, "path") && t.uint32(16).int32(e.path),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n, r, o = void 0 === t ? e.len : e.pos + t, i = new $root.im_proto.MsgTrace; e.pos < o; ) {
                        var a = e.uint32();
                        switch (a >>> 3) {
                        case 1:
                            i.metrics === $util.emptyObject && (i.metrics = {});
                            var s = e.uint32() + e.pos;
                            for (n = 0,
                            r = 0; e.pos < s; ) {
                                var c = e.uint32();
                                switch (c >>> 3) {
                                case 1:
                                    n = e.int32();
                                    break;
                                case 2:
                                    r = e.int64();
                                    break;
                                default:
                                    e.skipType(7 & c)
                                }
                            }
                            i.metrics[n] = r;
                            break;
                        case 2:
                            i.path = e.int32();
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
            "GetConversationParticipantsReadIndexV3ResponseBody":function() {
                function e(e) {
                    if (this.indexes = [],
                    e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.indexes = $util.emptyArray,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    if (t || (t = $Writer.create()),
                    null != e.indexes && e.indexes.length)
                        for (var n = 0; n < e.indexes.length; ++n)
                            $root.im_proto.ParticipantReadIndex.encode(e.indexes[n], t.uint32(10).fork()).ldelim();
                    return t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.GetConversationParticipantsReadIndexV3ResponseBody; e.pos < n; ) {
                        var o = e.uint32();
                        if (o >>> 3 == 1)
                            r.indexes && r.indexes.length || (r.indexes = []),
                            r.indexes.push($root.im_proto.ParticipantReadIndex.decode(e, e.uint32()));
                        else
                            e.skipType(7 & o)
                    }
                    return r
                }
                ,
                e
            }(),
            "ParticipantReadIndex": function() {
                function e(e) {
                    if (e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.user_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.sec_uid = "",
                e.prototype.index = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.index_v2 = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.index_min = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.group_index = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    return t || (t = $Writer.create()),
                    null != e.user_id && Object.hasOwnProperty.call(e, "user_id") && t.uint32(8).int64(e.user_id),
                    null != e.sec_uid && Object.hasOwnProperty.call(e, "sec_uid") && t.uint32(18).string(e.sec_uid),
                    null != e.index && Object.hasOwnProperty.call(e, "index") && t.uint32(24).int64(e.index),
                    null != e.index_v2 && Object.hasOwnProperty.call(e, "index_v2") && t.uint32(32).int64(e.index_v2),
                    null != e.index_min && Object.hasOwnProperty.call(e, "index_min") && t.uint32(40).int64(e.index_min),
                    null != e.group_index && Object.hasOwnProperty.call(e, "group_index") && t.uint32(48).int64(e.group_index),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.ParticipantReadIndex; e.pos < n; ) {
                        var o = e.uint32();
                        switch (o >>> 3) {
                        case 1:
                            r.user_id = e.int64();
                            break;
                        case 2:
                            r.sec_uid = e.string();
                            break;
                        case 3:
                            r.index = e.int64();
                            break;
                        case 4:
                            r.index_v2 = e.int64();
                            break;
                        case 5:
                            r.index_min = e.int64();
                            break;
                        case 6:
                            r.group_index = e.int64();
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
            "GetOpenConvsResponseBody":function() {
                function e(e) {
                    if (this.open_convs = [],
                    e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.next_openconv_version = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.open_conv_has_more = !1,
                e.prototype.open_convs = $util.emptyArray,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    if (t || (t = $Writer.create()),
                    null != e.next_openconv_version && Object.hasOwnProperty.call(e, "next_openconv_version") && t.uint32(8).int64(e.next_openconv_version),
                    null != e.open_conv_has_more && Object.hasOwnProperty.call(e, "open_conv_has_more") && t.uint32(16).bool(e.open_conv_has_more),
                    null != e.open_convs && e.open_convs.length)
                        for (var n = 0; n < e.open_convs.length; ++n)
                            $root.im_proto.OpenConvsBody.encode(e.open_convs[n], t.uint32(26).fork()).ldelim();
                    return t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n = void 0 === t ? e.len : e.pos + t, r = new $root.im_proto.GetOpenConvsResponseBody; e.pos < n; ) {
                        var o = e.uint32();
                        switch (o >>> 3) {
                        case 1:
                            r.next_openconv_version = e.int64();
                            break;
                        case 2:
                            r.open_conv_has_more = e.bool();
                            break;
                        case 3:
                            r.open_convs && r.open_convs.length || (r.open_convs = []),
                            r.open_convs.push($root.im_proto.OpenConvsBody.decode(e, e.uint32()));
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
            "NewP2PMessageNotify": function() {
                function e(e) {
                    if (this.ext = {},
                    e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.send_type = 0,
                e.prototype.sender = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.sec_sender = "",
                e.prototype.conversation_id = "",
                e.prototype.conversation_short_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.conversation_type = 0,
                e.prototype.message_type = 0,
                e.prototype.content = "",
                e.prototype.ext = $util.emptyObject,
                e.prototype.create_time = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    if (t || (t = $Writer.create()),
                    null != e.send_type && Object.hasOwnProperty.call(e, "send_type") && t.uint32(8).int32(e.send_type),
                    null != e.sender && Object.hasOwnProperty.call(e, "sender") && t.uint32(16).int64(e.sender),
                    null != e.sec_sender && Object.hasOwnProperty.call(e, "sec_sender") && t.uint32(26).string(e.sec_sender),
                    null != e.conversation_id && Object.hasOwnProperty.call(e, "conversation_id") && t.uint32(34).string(e.conversation_id),
                    null != e.conversation_short_id && Object.hasOwnProperty.call(e, "conversation_short_id") && t.uint32(40).int64(e.conversation_short_id),
                    null != e.conversation_type && Object.hasOwnProperty.call(e, "conversation_type") && t.uint32(48).int32(e.conversation_type),
                    null != e.message_type && Object.hasOwnProperty.call(e, "message_type") && t.uint32(56).int32(e.message_type),
                    null != e.content && Object.hasOwnProperty.call(e, "content") && t.uint32(66).string(e.content),
                    null != e.ext && Object.hasOwnProperty.call(e, "ext"))
                        for (var n = Object.keys(e.ext), r = 0; r < n.length; ++r)
                            t.uint32(74).fork().uint32(10).string(n[r]).uint32(18).string(e.ext[n[r]]).ldelim();
                    return null != e.create_time && Object.hasOwnProperty.call(e, "create_time") && t.uint32(80).int64(e.create_time),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n, r, o = void 0 === t ? e.len : e.pos + t, i = new $root.im_proto.NewP2PMessageNotify; e.pos < o; ) {
                        var a = e.uint32();
                        switch (a >>> 3) {
                        case 1:
                            i.send_type = e.int32();
                            break;
                        case 2:
                            i.sender = e.int64();
                            break;
                        case 3:
                            i.sec_sender = e.string();
                            break;
                        case 4:
                            i.conversation_id = e.string();
                            break;
                        case 5:
                            i.conversation_short_id = e.int64();
                            break;
                        case 6:
                            i.conversation_type = e.int32();
                            break;
                        case 7:
                            i.message_type = e.int32();
                            break;
                        case 8:
                            i.content = e.string();
                            break;
                        case 9:
                            i.ext === $util.emptyObject && (i.ext = {});
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
                            i.ext[n] = r;
                            break;
                        case 10:
                            i.create_time = e.int64();
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
            "Response": function() {
                function e(e) {
                    if (this.headers = {},
                    e)
                        for (var t = Object.keys(e), n = 0; n < t.length; ++n)
                            null != e[t[n]] && (this[t[n]] = e[t[n]])
                }
                return e.prototype.cmd = 0,
                e.prototype.sequence_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.status_code = 0,
                e.prototype.error_desc = "",
                e.prototype.inbox_type = 0,
                e.prototype.body = null,
                e.prototype.log_id = "",
                e.prototype.headers = $util.emptyObject,
                e.prototype.start_time_stamp = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.request_arrived_time = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.server_execution_end_time = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.prototype.retry_count = 0,
                e.prototype.req_user_id = $util.Long ? $util.Long.fromBits(0, 0, !1) : 0,
                e.create = function(t) {
                    return new e(t)
                }
                ,
                e.encode = function(e, t) {
                    if (t || (t = $Writer.create()),
                    null != e.cmd && Object.hasOwnProperty.call(e, "cmd") && t.uint32(8).int32(e.cmd),
                    null != e.sequence_id && Object.hasOwnProperty.call(e, "sequence_id") && t.uint32(16).int64(e.sequence_id),
                    null != e.status_code && Object.hasOwnProperty.call(e, "status_code") && t.uint32(24).int32(e.status_code),
                    null != e.error_desc && Object.hasOwnProperty.call(e, "error_desc") && t.uint32(34).string(e.error_desc),
                    null != e.inbox_type && Object.hasOwnProperty.call(e, "inbox_type") && t.uint32(40).int32(e.inbox_type),
                    null != e.body && Object.hasOwnProperty.call(e, "body") && $root.im_proto.ResponseBody.encode(e.body, t.uint32(50).fork()).ldelim(),
                    null != e.log_id && Object.hasOwnProperty.call(e, "log_id") && t.uint32(58).string(e.log_id),
                    null != e.headers && Object.hasOwnProperty.call(e, "headers"))
                        for (var n = Object.keys(e.headers), r = 0; r < n.length; ++r)
                            t.uint32(66).fork().uint32(10).string(n[r]).uint32(18).string(e.headers[n[r]]).ldelim();
                    return null != e.start_time_stamp && Object.hasOwnProperty.call(e, "start_time_stamp") && t.uint32(72).int64(e.start_time_stamp),
                    null != e.request_arrived_time && Object.hasOwnProperty.call(e, "request_arrived_time") && t.uint32(80).int64(e.request_arrived_time),
                    null != e.server_execution_end_time && Object.hasOwnProperty.call(e, "server_execution_end_time") && t.uint32(88).int64(e.server_execution_end_time),
                    null != e.retry_count && Object.hasOwnProperty.call(e, "retry_count") && t.uint32(96).int32(e.retry_count),
                    null != e.req_user_id && Object.hasOwnProperty.call(e, "req_user_id") && t.uint32(104).int64(e.req_user_id),
                    t
                }
                ,
                e.decode = function(e, t) {
                    e instanceof $Reader || (e = $Reader.create(e));
                    for (var n, r, o = void 0 === t ? e.len : e.pos + t, i = new $root.im_proto.Response; e.pos < o; ) {
                        var a = e.uint32();
                        switch (a >>> 3) {
                        case 1:
                            i.cmd = e.int32();
                            break;
                        case 2:
                            i.sequence_id = e.int64();
                            break;
                        case 3:
                            i.status_code = e.int32();
                            break;
                        case 4:
                            i.error_desc = e.string();
                            break;
                        case 5:
                            i.inbox_type = e.int32();
                            break;
                        case 6:
                            i.body = $root.im_proto.ResponseBody.decode(e, e.uint32());
                            break;
                        case 7:
                            i.log_id = e.string();
                            break;
                        case 8:
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
                        case 9:
                            i.start_time_stamp = e.int64();
                            break;
                        case 10:
                            i.request_arrived_time = e.int64();
                            break;
                        case 11:
                            i.server_execution_end_time = e.int64();
                            break;
                        case 12:
                            i.retry_count = e.int32();
                            break;
                        case 13:
                            i.req_user_id = e.int64();
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
        }
    };


function deserialize(t) {
            const n = new Uint8Array(t);
            return $root.im_proto.Response.decode(n)
        };


function deserializeFrame(t){
    const n =  new Uint8Array(t.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    return $root.im_proto.Frame.decode(n)
}


function receiveRaw(data) {
    const frame = deserializeFrame(data)
    if (frame.payload_type === "json") {
        return JSON.parse(Buffer.from(frame.payload).toString("utf8"));
    }
    const l = deserialize(frame.payload);
    return  JSON.parse(JSON.stringify($root.im_proto.Response.create(l)));
}


// da = "08b9d6f0b30410e3ef92d5c6f7fea81818914e20012a1a0a15785f66726f6e746965725f617272697665726174651201312a280a18785f66726f6e746965725f72656369657665645f74696d65120c6462626570346775756576612a4b0a12785f66726f6e746965725f74726163656964123530323137353234353835313636383230303030303030303030303030303030303030306666666630616433363934626530643663382a360a123a785f66726f6e746965725f6d73675f696412206d73675f6462626570346775746d7568303030326c3634706f613730677375322a290a193a785f66726f6e746965725f6d73675f73656e645f74696d65120c646262657034677769396c632a460a0b7472616365706172656e74123730302d65393132333438366438363063323733303433393536383263366666333765652d383939656563316561633035636535352d303132003a02706242d80508f4031000180022002803328c05a21f88051225323231363235363637393138343837323a32393431313339303a3a323a313a706967656f6e180b20012afb030a25323231363235363637393138343837323a32393431313339303a3a323a313a706967656f6e100b188a9084a2c3a299ba682000289b8a87a6bbf796b16830d18603380042cd017b22636f6d6d616e645f74797065223a362c22636f6e766572736174696f6e5f6964223a22323231363235363637393138343837323a32393431313339303a3a323a313a706967656f6e222c22636f6e766572736174696f6e5f74797065223a31312c2267726f75705f76657273696f6e223a313735323435383532362c22696e626f785f74797065223a332c227375625f636f6e5f6964223a22333a37353236373531393338353636373531343938222c2276657273696f6e223a313735323435383531363532363138367d4a0f0a0a733a6e6565645f6263701201314a3b0a13733a636c69656e745f6d6573736167655f6964122439656536633638312d373830662d346431322d393433352d3963333762393235343539314a170a0c733a626173655f7363656e65120764656661756c744a140a0e733a6d73675f7072696f7269747912022d314a130a0e733a636f6d6d616e645f7479706512013650cab0abb5803358006000680072374d5334774c6a4142414141414e776b4a75574952464f7a67357543704452704d6a344f582d5172796f44676e2d79596c58516e52775151880100a0018a8a84d6a7a099ba6830e89ffadaa0bb8e033884ddfadaa0bb8e034000480060873f72360a0b080710bfa0fbdaa0bb8e030a0b080310b5c3f3daa0bb8e030a0b080410d3b2f9daa0bb8e030a0b0805108afef9daa0bb8e031000a0018a8a84d6a7a099ba68b201003a35303231373532343538353135383736303030303030303030303030303030303030303066666666306164303430616536363666633048c8b1abb580334a353032313735323435383531363638323030303030303030303030303030303030303030666666663061643336393462653064366338521a6261636b626f6e653b7374613d313735323435383531363638325a206d73675f6462626570346775746d7568303030326c3634706f613730677375326000"

// console.log(receiveRaw(da))
