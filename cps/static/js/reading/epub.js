/* global $, calibre, EPUBJS, ePubReader */

var reader;

(function() {
    "use strict";

    EPUBJS.filePath = calibre.filePath;
    EPUBJS.cssPath = calibre.cssPath;

    reader = ePubReader(calibre.bookUrl, {
        restore: true,
        bookmarks: calibre.bookmark ? [calibre.bookmark] : []
    });

    Object.keys(themes).forEach(function (theme) {
        reader.rendition.themes.register(theme, themes[theme].css_path);
    });

    if (calibre.useBookmarks) {
        reader.on("reader:bookmarked", updateBookmark.bind(reader, "add"));
        reader.on("reader:unbookmarked", updateBookmark.bind(reader, "remove"));
    } else {
        $("#bookmark, #show-Bookmarks").remove();
    }

    // Enable swipe support
    // I have no idea why swiperRight/swiperLeft from plugins is not working, events just don't get fired
    var touchStart = 0;
    var touchEnd = 0;

    reader.rendition.on('touchstart', function(event) {
        touchStart = event.changedTouches[0].screenX;
    });
    reader.rendition.on('touchend', function(event) {
      touchEnd = event.changedTouches[0].screenX;
        if (touchStart < touchEnd) {
            if(reader.book.package.metadata.direction === "rtl") {
    			reader.rendition.next();
    		} else {
    			reader.rendition.prev();
    		}
            // Swiped Right
        }
        if (touchStart > touchEnd) {
            if(reader.book.package.metadata.direction === "rtl") {
    			reader.rendition.prev();
    		} else {
                reader.rendition.next();
    		}
            // Swiped Left
        }
    });

    // 进度同步相关变量
    let progressDiv = document.getElementById("progress");
    let lastSavedTime = 0; // 防抖：记录上次保存时间
    const SYNC_INTERVAL = 30000; // 30秒保存一次

    // 初始化时加载历史进度
    function loadProgress() {
        // 从calibre对象获取书籍ID和格式（需模板提前注入calibre.bookId/calibre.bookFormat）
        const bookId = calibre.bookId || "{{ bookid }}";
        const format = calibre.bookFormat || "{{ book_format }}";
        
        $.getJSON(`/ajax/get_progress/${bookId}/${format}`, function(data) {
            if (data.status === "success" && data.progress) {
                // 恢复到上次阅读位置
                reader.rendition.display(data.progress);
                console.log("已加载历史阅读进度");
            }
        }).fail(function(xhr, status, error) {
            console.error("加载进度失败:", error);
        });
    }

    // 保存当前进度到后端
    function saveProgress(location) {
        const now = Date.now();
        // 防抖：30秒内不重复保存
        if (now - lastSavedTime < SYNC_INTERVAL) return;

        const bookId = calibre.bookId || "{{ bookid }}";
        const format = calibre.bookFormat || "{{ book_format }}";
        const progressCFI = location.end.cfi; // EPUB的CFI定位标识
        const progressPercent = Math.round(location.end.percentage * 100);

        const csrftoken = $("input[name='csrf_token']").val();
        
        $.ajax({
            url: "/ajax/save_progress",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                book_id: bookId,
                format: format,
                progress: progressCFI,
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
                console.log("进度保存成功");
            },
            fail: function(xhr, status, error) {
                console.error("保存进度失败:", error);
            }
        });
    }

    // Update progress percentage & 进度同步逻辑
    reader.book.ready.then((()=>{
        let locations_key = reader.book.key()+'-locations';
        let stored_locations = localStorage.getItem(locations_key);
        let make_locations, save_locations;
        if (stored_locations) {
            make_locations = Promise.resolve(reader.book.locations.load(stored_locations));
            // No-op because locations are already saved
            save_locations = ()=>{};
        } else {
            make_locations = reader.book.locations.generate();
            save_locations = ()=>{
                localStorage.setItem(locations_key, reader.book.locations.save());
            };
        }
        make_locations.then(()=>{
            // 监听位置变化事件（relocated等价于locationChanged）
            reader.rendition.on('relocated', (location)=>{
                let percentage = Math.round(location.end.percentage*100);
                progressDiv.textContent=percentage+"%";
                
                // 位置变化时保存进度
                saveProgress(location);
            });
            
            // 初始化时加载历史进度
            loadProgress();

            reader.rendition.reportLocation();
            progressDiv.style.visibility = "visible";
        }).then(save_locations);
    }));

    /**
     * @param {string} action - Add or remove bookmark
     * @param {string|int} location - Location or zero
     */
    function updateBookmark(action, location) {
        // Remove other bookmarks (there can only be one)
        if (action === "add") {
            this.settings.bookmarks.filter(function (bookmark) {
                return bookmark && bookmark !== location;
            }).map(function (bookmark) {
                this.removeBookmark(bookmark);
            }.bind(this));
        }
        
        var csrftoken = $("input[name='csrf_token']").val();

        // Save to database
        $.ajax(calibre.bookmarkUrl, {
            method: "post",
            data: { bookmark: location || "" },
            headers: { "X-CSRFToken": csrftoken }
        }).fail(function (xhr, status, error) {
            alert(error);
        });
    }

    // 页面关闭/刷新时强制保存进度
    window.addEventListener('beforeunload', function() {
        const currentLocation = reader.rendition.currentLocation();
        if (currentLocation) {
            saveProgress(currentLocation);
        }
    });
    
    // Default settings load
    const theme = localStorage.getItem("calibre.reader.theme") ?? "lightTheme";
    selectTheme(theme);
})();