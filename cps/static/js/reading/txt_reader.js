/* This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
 *    Copyright (C) 2021 Ozzieisaacs
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program. If not, see <http://www.gnu.org/licenses/>.
 */

$(document).ready(function() {
    // 进度同步相关变量
    const bookId = "{{ txtfile }}"; // 从模板获取书籍ID
    const format = "txt";
    let lastSavedTime = 0; // 防抖：上次保存时间
    const SYNC_INTERVAL = 30000; // 30秒保存一次
    let origwidth; // 提前声明，方便后续使用
    let gap = 20;

    // 加载保存的进度
    function loadTxtProgress() {
        $.getJSON(`/ajax/get_progress/${bookId}/${format}`, (data) => {
            if (data.status === "success" && data.progress) {
                // 恢复滚动位置（offset.left对应保存的scrollLeft偏移）
                const savedOffset = parseInt(data.progress);
                $("#content").offset({ left: -savedOffset }); // 注意TXT阅读器是通过offset控制位置，需取反
                updateTxtProgressDisplay(); // 恢复后更新进度显示
            }
        }).fail(function(xhr, status, error) {
            console.error("加载TXT进度失败:", error);
        });
    }

    // 保存当前进度到后端
    function saveTxtProgress() {
        const now = Date.now();
        // 防抖：30秒内不重复保存
        if (now - lastSavedTime < SYNC_INTERVAL) return;

        // 获取当前阅读位置（offset.left是负数，取绝对值为滚动偏移量）
        const scrollOffset = Math.abs(parseInt($("#content").offset().left));
        const totalWidth = $("#content")[0].scrollWidth;
        const progressPercent = totalWidth > 0 ? (scrollOffset / totalWidth) * 100 : 0;

        const csrftoken = $("input[name='csrf_token']").val();
        $.ajax({
            url: "/ajax/save_progress",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                book_id: bookId,
                format: format,
                progress: scrollOffset.toString(), // 保存滚动偏移量（绝对值）
                progress_percent: progressPercent
            }),
            headers: { "X-CSRFToken": csrftoken },
            success: function() {
                lastSavedTime = now;
                // 同步状态提示（需模板添加#sync-status元素）
                const syncStatus = document.getElementById("sync-status");
                if (syncStatus) {
                    syncStatus.style.display = "inline";
                    setTimeout(() => syncStatus.style.display = "none", 2000);
                }
                console.log("TXT进度保存成功");
            },
            fail: function(xhr, status, error) {
                console.error("保存TXT进度失败:", error);
            }
        });
    }

    // 更新进度显示
    function updateTxtProgressDisplay() {
        const scrollOffset = Math.abs(parseInt($("#content").offset().left));
        const totalWidth = $("#content")[0].scrollWidth;
        const percent = totalWidth > 0 ? Math.round((scrollOffset / totalWidth) * 100) : 0;
        const progressEl = document.getElementById("progress");
        if (progressEl) {
            progressEl.textContent = `${percent}%`;
        }
    }

    //to int
    $("#area").width($("#area").width());
    $("#content").width($("#content").width());
    
    //bind text
    $("#content").load($("#readmain").data('load'), function(textStr) {
        $(this).height($(this).parent().height()*0.95);
        $(this).text(textStr);
        origwidth = $("#content")[0].getBoundingClientRect().width; // 内容加载后初始化origwidth
        loadTxtProgress(); // 内容加载完成后加载进度
    });

    // 监听content位置变化（翻页/滚动）
    $("#content").on("scroll", function() {
        updateTxtProgressDisplay(); // 实时更新进度显示
        saveTxtProgress(); // 触发保存
    });

    //keybind
    $(document).keydown(function(event){
        if(event.keyCode == 37){
            prevPage();
            updateTxtProgressDisplay();
            saveTxtProgress(); // 翻页后保存
        }
        if(event.keyCode == 39){
            nextPage();
            updateTxtProgressDisplay();
            saveTxtProgress(); // 翻页后保存
        }
    });

    //click
    $( "#left" ).click(function() {
        prevPage();
        updateTxtProgressDisplay();
        saveTxtProgress(); // 点击翻页后保存
    });
    $( "#right" ).click(function() {
        nextPage();
        updateTxtProgressDisplay();
        saveTxtProgress(); // 点击翻页后保存
    });

    $("#readmain").swipe( {
        swipeRight:function() {
            prevPage();
            updateTxtProgressDisplay();
            saveTxtProgress(); // 滑动翻页后保存
        },
        swipeLeft:function() {
            nextPage();
            updateTxtProgressDisplay();
            saveTxtProgress(); // 滑动翻页后保存
        },
    });

    //bind mouse
    $(window).bind('DOMMouseScroll mousewheel', function(event) {
        var delta = 0;
        if (event.originalEvent.wheelDelta) {
            delta = event.originalEvent.wheelDelta;
        } else if (event.originalEvent.detail) {
            delta = event.originalEvent.detail*-1;
        }
        if (delta >= 0) {
            prevPage();
        } else {
            nextPage();
        }
        updateTxtProgressDisplay();
        saveTxtProgress(); // 滚轮翻页后保存
    });

    //page animate
    function prevPage() {
        if(!origwidth) return; // 确保origwidth已初始化
        if($("#content").offset().left > 0) {
            return;
        }
        let leftoff = $("#content").offset().left;
        leftoff = leftoff+origwidth+gap;
        $("#content").offset({left:leftoff});
    }

    function nextPage() {
        if(!origwidth) return; // 确保origwidth已初始化
        let leftoff = $("#content").offset().left;
        leftoff = leftoff-origwidth-gap;
        if (leftoff + $("#content")[0].scrollWidth < 0) {
            return;
        }
        $("#content").offset({left:leftoff});
    }

    // 页面关闭/刷新时强制保存进度
    window.addEventListener('beforeunload', function() {
        saveTxtProgress();
    });
});