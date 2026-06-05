/**
 * Fila visual de arquivos selecionados (dropzone + lista com remover individual).
 */
(function (global) {
    var EXT_LABELS = {
        pdf: 'PDF', doc: 'DOC', docx: 'DOCX', xls: 'XLS', xlsx: 'XLSX',
        jpg: 'JPG', jpeg: 'JPG', png: 'PNG', gif: 'GIF',
        zip: 'ZIP', rar: 'RAR', '7z': '7Z',
    };

    function formatBytes(bytes) {
        if (!bytes && bytes !== 0) return '—';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    }

    function fileExt(name) {
        var parts = (name || '').split('.');
        return parts.length > 1 ? parts.pop().toLowerCase() : 'file';
    }

    function fileKey(f) {
        return [f.name, f.size, f.lastModified].join('|');
    }

    /**
     * @param {ParentNode} scope
     * @param {{ inputSelector?: string, dropzoneSelector?: string, queueSelector?: string, queueListSelector?: string, queueClearSelector?: string }} opts
     */
    function initAnexosFileQueue(scope, opts) {
        opts = opts || {};
        var fileInput = scope.querySelector(opts.inputSelector || '#anexos');
        if (!fileInput) return;

        var dropzone = scope.querySelector(opts.dropzoneSelector || '#wo-anexos-dropzone');
        var queueWrap = scope.querySelector(opts.queueSelector || '#wo-anexos-queue');
        var queueList = scope.querySelector(opts.queueListSelector || '#wo-anexos-queue-list');
        var queueClear = scope.querySelector(opts.queueClearSelector || '#wo-anexos-queue-clear');
        var selectedFiles = [];

        function syncInputFiles() {
            var dt = new DataTransfer();
            selectedFiles.forEach(function (f) {
                dt.items.add(f);
            });
            fileInput.files = dt.files;
        }

        function updateDropzoneState() {
            if (dropzone) {
                dropzone.classList.toggle('upload-dropzone--compact', selectedFiles.length > 0);
            }
            if (queueWrap) {
                queueWrap.hidden = selectedFiles.length === 0;
            }
        }

        function removeFile(index) {
            selectedFiles.splice(index, 1);
            syncInputFiles();
            renderQueue();
        }

        function clearAll() {
            selectedFiles = [];
            syncInputFiles();
            renderQueue();
        }

        function addFilesFromList(fileList) {
            if (!fileList || !fileList.length) return;
            var keys = {};
            selectedFiles.forEach(function (f) {
                keys[fileKey(f)] = true;
            });
            for (var i = 0; i < fileList.length; i++) {
                var f = fileList[i];
                var k = fileKey(f);
                if (!keys[k]) {
                    selectedFiles.push(f);
                    keys[k] = true;
                }
            }
            syncInputFiles();
            renderQueue();
        }

        function renderQueue() {
            if (!queueList) {
                updateDropzoneState();
                return;
            }
            queueList.innerHTML = '';
            selectedFiles.forEach(function (file, index) {
                var ext = fileExt(file.name);
                var li = document.createElement('li');
                li.className = 'upload-file-card upload-file-card--pending';
                li.innerHTML =
                    '<div class="upload-file-card-icon upload-file-card-icon--' + ext + '" aria-hidden="true">' +
                    '<span>' + (EXT_LABELS[ext] || ext.toUpperCase().slice(0, 4) || '?') + '</span>' +
                    '</div>' +
                    '<div class="upload-file-card-body">' +
                    '<p class="upload-file-card-name" title="' + file.name.replace(/"/g, '&quot;') + '">' + file.name + '</p>' +
                    '<p class="upload-file-card-meta">' + formatBytes(file.size) + '</p>' +
                    '</div>' +
                    '<div class="upload-file-card-actions">' +
                    '<button type="button" class="upload-file-card-btn upload-file-card-btn--danger" data-index="' + index + '" aria-label="Remover ' + file.name.replace(/"/g, '') + '">Remover</button>' +
                    '</div>';
                queueList.appendChild(li);
            });
            queueList.querySelectorAll('[data-index]').forEach(function (btn) {
                btn.addEventListener('click', function (e) {
                    e.preventDefault();
                    removeFile(parseInt(btn.getAttribute('data-index'), 10));
                });
            });
            updateDropzoneState();
        }

        fileInput.addEventListener('change', function (e) {
            if (e.target.files && e.target.files.length) {
                addFilesFromList(e.target.files);
            }
        });

        if (queueClear) {
            queueClear.addEventListener('click', clearAll);
        }

        if (dropzone) {
            dropzone.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    fileInput.click();
                }
            });
            dropzone.addEventListener('dragover', function (e) {
                e.preventDefault();
                dropzone.classList.add('dragover');
            });
            dropzone.addEventListener('dragleave', function (e) {
                e.preventDefault();
                dropzone.classList.remove('dragover');
            });
            dropzone.addEventListener('drop', function (e) {
                e.preventDefault();
                dropzone.classList.remove('dragover');
                if (e.dataTransfer.files && e.dataTransfer.files.length) {
                    addFilesFromList(e.dataTransfer.files);
                }
            });
        }

        updateDropzoneState();
    }

    global.LplanAnexosFileQueue = initAnexosFileQueue;
})(typeof window !== 'undefined' ? window : this);
