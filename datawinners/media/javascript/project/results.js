$(document).ready(function () {
    var tab = ["all", "success", "error", "deleted"];

    var active_tab_index;

    function TabOptions() {
        var defaultOptions = {
            "show_status":true,
            "show_actions":true,
            "show_deleting_check_box":true,
            "show_reply_sms":false
        };
        this._options = {
            'all':defaultOptions,
            'success':$.extend({}, defaultOptions, {"show_status":false}),
            'error':$.extend({}, defaultOptions, {"show_status":false, "show_reply_sms":true}),
            'deleted':$.extend({}, defaultOptions, {"show_actions":false, "show_deleting_check_box":false})
        }
    }

    TabOptions.prototype.show_status = function () {
        return this._options[tab[active_tab_index]].show_status;
    }

    TabOptions.prototype.show_actions = function () {
        return this._options[tab[active_tab_index]].show_actions;
    }

    TabOptions.prototype.show_deleting_check_box = function () {
        return this._options[tab[active_tab_index]].show_deleting_check_box;
    }

    TabOptions.prototype.show_reply_sms = function () {
        return this._options[tab[active_tab_index]].show_reply_sms;
    }

    $.ajaxSetup({ cache:false });
    $(document).ajaxStop($.unblockUI);

    var $no_submission_hint = $('.help_no_submissions');
    var $page_hint = $('#page_hint');
    var message = gettext("No submissions available for this search. Try changing some of the filters.");
    var help_all_data_are_filtered = "<div class=\"help_accordion\" style=\"text-align: left;\">" + message + "</div>";
    var $filterSelects = $('#subjectSelect, #dataSenderSelect');

    (function buildFilters() {
        var subject_options = {emptyText:gettext("All") + ' ' + entity_type};
        var data_sender_options = {emptyText:gettext("All Data Senders")};
        var filter_options = [subject_options, data_sender_options];

        $filterSelects.each(function (index, filter) {
            $(filter).dropdownchecklist($.extend({firstItemChecksAll:false,
                explicitClose:gettext("OK"),
                explicitClear:gettext("Clear"),
                width:$(this).width(),
                eventCallback:function () {
                    $('.ui-daterangepicker:visible').hide();
                },
                maxDropHeight:200}, filter_options[index]));

        });
    })();

    buildRangePicker();
    var tabOptions = new TabOptions();
    $("#tabs").tabs().find('>ul>li>a').click(function () {
        var tab_index = $(this).parent().index();

        if (active_tab_index === tab_index) {
            return;
        }
        active_tab_index = tab_index;

        if (tabOptions.show_actions()) {
            $('.action_container').css('visibility', 'visible');
        } else {
            $('.action_container').css('visibility', 'hidden');
        }
        fetch_data(tab_index);
    }).filter(':first').trigger('click');

    $(".ui-corner-all").removeClass("ui-corner-all");
    $(".ui-corner-top").removeClass("ui-corner-top");

    function buildRangePicker() {
        $('#reportingPeriodPicker').datePicker({header:gettext('All Periods')});
        $('#submissionDatePicker').datePicker();
    }

    $('#go').click(function () {
        fetch_data(active_tab_index);
    });

    $('.export_link').click(function () {
        var url = '/project/export/log' + '?type=' + tab[active_tab_index];
        $('#export_form').appendJson(DW.get_criteria()).attr('action', url).submit();
    });

    function fetch_data(active_tab_index) {
        var data = DW.get_criteria();
        DW.loading();
        $.ajax({
            type:'POST',
            url:window.location.pathname + '?type=' + tab[active_tab_index],
            data:data,
            success:function (response) {
                var response_data = JSON.parse(response);
                show_data(active_tab_index, response_data.data_list);
                $(".action_container").parent().clone(true).addClass("margin_top_null").appendTo(".data_table");
            }});
    }

    function dataBinding(data, destroy, retrive, emptyTableText) {
        $('.submission_table').dataTable({
            "bDestroy":destroy,
            "bRetrieve":retrive,
            "sPaginationType":"full_numbers",
            "aaData":data,
            "bSort":false,
            "aoColumnDefs":[
                {
                    "fnRender":function (oObj) {
                        return '<input type="checkbox" value="' + oObj.aData[0] + '" class="selected_submissions"/>';
                    },
                    "aTargets":[0],
                    'bVisible':tabOptions.show_deleting_check_box()
                },
                {
                    "bVisible":tabOptions.show_status(),
                    "aTargets":[3]
                },
                {
                    "bVisible":tabOptions.show_reply_sms(),
                    "aTargets":[4]
                }
            ],
            "fnHeaderCallback":function (nHead, aData, iStart, iEnd, aiDisplay) {
                if (tabOptions.show_deleting_check_box()) {
                    nHead.getElementsByTagName('th')[0].innerHTML = '<input type="checkbox" id="master_checkbox"/>';
                }
            },
            "oLanguage":{
                "sProcessing":gettext("Processing..."),
                "sLengthMenu":gettext("Show _MENU_ Submissions"),
                "sZeroRecords":emptyTableText,
                "sEmptyTable":emptyTableText,
                "sLoadingRecords":gettext("Loading..."),
                "sInfo":gettext("<span class='bold'>_START_ - _END_</span> of <span id='total_count'>_TOTAL_</span> Submissions"),
                "sInfoEmpty":gettext("0 Submissions"),
                "sInfoFiltered":gettext("(filtered from _MAX_ total Data records)"),
                "sInfoPostFix":"",
                "sSearch":gettext("Search:"),
                "sUrl":"",
                "oPaginate":{
                    "sFirst":gettext("First"),
                    "sPrevious":gettext("Previous"),
                    "sNext":gettext("Next"),
                    "sLast":gettext("Last")
                },
                "fnInfoCallback":null
            },
            "sDom":'<"@dataTables_info"i>rtpl',
            "iDisplayLength":25
        });
    }

    function show_data(active_tab_index, data) {
        var index = (active_tab_index || 0) + 1;
        var with_or_without_data = (data.length) ? "with_data" : "no_data";
        var hint = DW.hint[active_tab_index][with_or_without_data];
        if (hint) {
            $("#page_hint").find("div").eq(active_tab_index).html(hint);
        }
        $page_hint.find('>div:nth-child(' + index + ')').show().siblings().hide();
        dataBinding(data, true, false, getEmptyTableText());
        wrap_table();
    }

    function getEmptyTableText() {
        return isFiltering() ? help_all_data_are_filtered : $no_submission_hint.filter(':eq(' + active_tab_index + ')').html();
    }

    function isFiltering() {
        return _.any(_.values(DW.get_criteria()), function (v) {
            return !_.isUndefined(v) && !_.isEmpty($.trim(v))
        })
    }

    function wrap_table() {
        $(".submission_table").wrap("<div class='data_table' style='width:" + ($(window).width() - 65) + "px'/>");
    }

    DW.hint = [
        {"with_data":"", "no_data":""},
        {"with_data":"", "no_data":""},
        {"with_data":gettext("View and manage unsuccessful Submissions for this project"), "no_data":gettext("No unsuccessful Submissions!") }
    ]
    DW.get_ids = function () {
        var ids = [];
        $(".selected_submissions:checked").each(function () {
            if ($(this).val() != "None") {
                ids.push($(this).val());
            }
        });
        return ids;
    }

    //Checkbox on/off functionality
    $("#master_checkbox").live("click", function () {
        var status = $(this).attr('checked');
        $(".selected_submissions").each(function () {
            $(this).attr("checked", status);
        });

    });

    $('select.action').live("change", function () {
        var ids = DW.get_ids();
        if ($(".selected_submissions:checked").length == 0) {
            $("#message_text").html("<div class='message message-box'>" + gettext("Please select atleast one undeleted record") + "</div>");
            $('select.action>option:first').attr('selected', 'selected');
        } else {
            if (ids.length == 0) {
                $("#message_text").html("<div class='message message-box'>" + gettext("This data has already been deleted") + "</div>");
                $('select.action>option:first').attr('selected', 'selected');
            } else {
                DW.delete_submission_warning_dialog.show_warning();
                DW.delete_submission_warning_dialog.ids = ids;
            }
        }
        $("#message_text .message").delay(5000).fadeOut();
    });

    var kwargs = {container:"#delete_submission_warning_dialog",
        continue_handler:function () {
            var ids = this.ids;
            $.blockUI({ message:'<h1><img src="/media/images/ajax-loader.gif"/><span class="loading">' + gettext("Just a moment") + '...</span></h1>', css:{ width:'275px'}});
            $.ajax({
                type:'POST',
                url:window.location.pathname + "?rand=" + new Date().getTime(),
                data:{'id_list':JSON.stringify(ids), 'page_number':DW.current_page},
                success:function (response) {
                    var data = JSON.parse(response);
                    if (data.success) {
                        $("#message_text").html("<div class='message success-box'>" + data.success_message + "</div>");
                        fetch_data(0);
                    } else {
                        $("#message_text").html("<div class='error_message message-box'>" + data.error_message + "</div>");
                    }
                    $("#message_text .message").delay(5000).fadeOut();
                    $('select.action>option:first').attr('selected', 'selected');
                    $.unblockUI();
                },
                error:function (e) {
                    $("#message_text").html("<div class='error_message message-box'>" + e.responseText + "</div>");
                    $('select.action>option:first').attr('selected', 'selected');
                    $.unblockUI();
                }
            });
            return false;
        },
        title:gettext("Your Submission(s) will be deleted"),
        cancel_handler:function () {
            $('select.action>option:first').attr('selected', 'selected');
        },
        height:150,
        width:550
    }

    DW.delete_submission_warning_dialog = new DW.warning_dialog(kwargs);

});
