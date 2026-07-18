
        (function() {{
            var doc = window.parent.document;
            var ctxMsgs = {_pet_ctx_msgs};
            var petMsgs = {_pet_pet_msgs};
            var bodyMsgs = {_pet_body_msgs};
            var tailMsgs = {_pet_tail_msgs};
            var quickQuestions = {_pet_quick_qs};
            var petType = '{_pet_type}';
            var petId = 'sp-pet-pos-{_pet_type}';

            // Global state namespace — survives Streamlit reruns
            var NS = window.parent.__spPetNS || (window.parent.__spPetNS = {{}});
            NS.ctxMsgs = ctxMsgs; NS.petMsgs = petMsgs; NS.bodyMsgs = bodyMsgs; NS.tailMsgs = tailMsgs;
            NS.quickQuestions = quickQuestions; NS.petType = petType; NS.petId = petId;

            function initPet() {{
                var pet = doc.getElementById('spPet');
                var bubble = doc.getElementById('spPetBubble');
                if (!pet || !bubble) return false;
                if (pet.__spBound) return true;  // already bound to this DOM element

                pet.__spBound = true;
                var msgIdx = 0;
                var bubbleTimer = null, moodTimer = null, idleTimer = null;
                var isDragging = false, dragMoved = false;
                var startX, startY, origLeft, origTop;
                var headPetCount = 0, headPetTimer = null, clickTimer = null;
                var quickPanelOpen = false;

                function show(text, duration) {{
                    bubble.textContent = text;
                    bubble.classList.add('sp-show');
                    if (bubbleTimer) clearTimeout(bubbleTimer);
                    bubbleTimer = setTimeout(function() {{ bubble.classList.remove('sp-show'); }}, duration || 3500);
                }}
                function setMood(cls, duration) {{
                    pet.classList.remove('sp-happy','sp-angry','sp-sleepy','sp-wag','sp-hearts','sp-purr','sp-wave');
                    if (cls) pet.classList.add(cls);
                    if (moodTimer) clearTimeout(moodTimer);
                    if (duration && cls) moodTimer = setTimeout(function() {{ pet.classList.remove(cls); }}, duration);
                }}
                function resetIdle() {{
                    if (idleTimer) clearTimeout(idleTimer);
                    pet.classList.remove('sp-sleepy');
                    idleTimer = setTimeout(function() {{
                        setMood('sp-sleepy');
                        show(['zzz...','好困...要打盹了...','休眠中...轻点打扰~'][Math.floor(Math.random()*3)], 2500);
                    }}, 45000);
                }}
                function pick(a) {{ return a[Math.floor(Math.random()*a.length)]; }}

                // Quick panel
                var quickPanel = doc.getElementById('spPetQuickPanel');
                var quickItems = doc.getElementById('spPetQuickItems');
                function renderQuickItems() {{
                    if (!quickItems || !quickQuestions || !quickQuestions.length) return;
                    quickItems.innerHTML = '';
                    quickQuestions.forEach(function(q) {{
                        var div = doc.createElement('div');
                        div.className = 'sp-pet-quick-item';
                        div.textContent = q;
                        div.onclick = function(e) {{
                            e.stopPropagation();
                            if (window.parent.streamlitSyncMsg) window.parent.streamlitSyncMsg('pet_quick_q', q);
                            window.parent.dispatchEvent(new CustomEvent('spPetQuickQuestion', {{detail: q}}));
                            setMood('sp-happy', 1500);
                            show('好的～这就帮你问！', 2000);
                            toggleQuickPanel(false);
                            resetIdle();
                        }};
                        quickItems.appendChild(div);
                    }});
                }}
                function toggleQuickPanel(force) {{
                    if (!quickPanel) return;
                    var showIt = (typeof force === 'boolean') ? force : !quickPanelOpen;
                    quickPanelOpen = showIt;
                    if (showIt) {{ quickPanel.classList.add('sp-show'); setMood('sp-wag', 1200); }}
                    else {{ quickPanel.classList.remove('sp-show'); }}
                }}
                window.parent.spToggleQuickPanel = function() {{ toggleQuickPanel(false); }};
                window.parent.spUpdatePetQuickQuestions = function(qs) {{ quickQuestions = qs || []; renderQuickItems(); }};
                window.parent.spPetTalk = function() {{ setMood('sp-wag',1200); show(ctxMsgs[msgIdx%ctxMsgs.length],4000); msgIdx++; resetIdle(); }};

                // Right-click → quick panel
                pet.addEventListener('contextmenu', function(e) {{ e.preventDefault(); toggleQuickPanel(); setMood('sp-wag',1000); resetIdle(); }});

                // Hint button
                var hintBtn = doc.getElementById('spPetHintBtn');
                if (hintBtn) {{
                    hintBtn.onclick = function(e) {{ e.stopPropagation(); e.preventDefault(); toggleQuickPanel(); setMood('sp-happy',1000); resetIdle(); }};
                }}

                // Triple-click → quick panel
                var tripleCount = 0, tripleTimer = null;
                pet.addEventListener('click', function(e) {{
                    tripleCount++;
                    if (tripleTimer) clearTimeout(tripleTimer);
                    tripleTimer = setTimeout(function() {{ tripleCount = 0; }}, 600);
                    if (tripleCount >= 3) {{ tripleCount = 0; toggleQuickPanel(); }}
                }});

                // Hit area detection
                function distToRect(px, py, rect) {{
                    var cx = Math.max(rect.left, Math.min(px, rect.right));
                    var cy = Math.max(rect.top, Math.min(py, rect.bottom));
                    return Math.hypot(px - cx, py - cy);
                }}
                function hitArea(e) {{
                    var r = pet.getBoundingClientRect();
                    var y = e.clientY - r.top;
                    var tailGroups = pet.querySelectorAll('.sp-pet-tail-group');
                    var closestDist = Infinity;
                    for (var i = 0; i < tailGroups.length; i++) {{
                        var d = distToRect(e.clientX, e.clientY, tailGroups[i].getBoundingClientRect());
                        if (d < closestDist) closestDist = d;
                    }}
                    if (closestDist < 22) return 'tail';
                    if (y < r.height * 0.55) return 'head';
                    if (y > r.height * 0.82) return 'tail';
                    return 'body';
                }}
                var specialMsgs = {{
                    "cat": ["喵呜～最爱你了！♡♡♡","咕噜咕噜咕噜…超级幸福！","在你身上踩奶踩奶！🐾","翻肚皮！要一直摸！","喵——！你是我的主人！♡"],
                    "penguin": ["咕噜咕噜～你是我最好的朋友！","要不要一起去滑冰？❄️","企鹅抱抱！🤗"],
                    "dog": ["汪汪汪！最最最喜欢你！！","舔舔舔～你是我的全世界！","翻肚皮！要摸摸！🐾"],
                    "robot": ["情感模块输出：最高级喜悦。","系统提示：你是一个优秀的操作者。","检测到幸福指数飙升！✨"]
                }};
                function onDblClick(e) {{
                    if (dragMoved) return;
                    var msgs = specialMsgs[petType] || specialMsgs.cat;
                    setMood('sp-happy', 2000);
                    if (petType === 'cat') {{
                        pet.classList.add('sp-hearts'); pet.classList.add('sp-purr');
                        setTimeout(function() {{ pet.classList.remove('sp-hearts'); }}, 1500);
                        setTimeout(function() {{ pet.classList.remove('sp-purr'); }}, 3000);
                    }}
                    show(pick(msgs), 3500); resetIdle();
                }}
                function onClick(e) {{
                    if (dragMoved) {{ dragMoved = false; return; }}
                    if (clickTimer) {{ clearTimeout(clickTimer); clickTimer = null; onDblClick(e); return; }}
                    clickTimer = setTimeout(function() {{
                        clickTimer = null;
                        if (dragMoved) {{ dragMoved = false; return; }}
                        var a = hitArea(e);
                        if (a === 'head') {{
                            setMood('sp-happy',1500); show(pick(petMsgs),3000);
                            if (petType === 'cat') {{
                                headPetCount++;
                                if (headPetTimer) clearTimeout(headPetTimer);
                                headPetTimer = setTimeout(function() {{ headPetCount = 0; }}, 3000);
                                if (headPetCount >= 3) {{
                                    pet.classList.add('sp-hearts'); pet.classList.add('sp-purr');
                                    setTimeout(function() {{ pet.classList.remove('sp-hearts'); }}, 1500);
                                    setTimeout(function() {{ pet.classList.remove('sp-purr'); }}, 3000);
                                    headPetCount = 0;
                                    bubble.classList.remove('sp-show');
                                    setTimeout(function() {{ show(pick(["咕噜咕噜咕噜！最爱你了喵♡","呼噜…完全被驯服了…","喵呜～摸头杀！出爱心了！❤"]), 3000); }}, 400);
                                }}
                            }}
                        }} else if (a === 'tail') {{
                            setMood('sp-angry',1200); show(pick(tailMsgs),3000); headPetCount = 0;
                        }} else {{
                            setMood('sp-wag',1200); show(pick(bodyMsgs),3000);
                            if (petType === 'cat') {{ pet.classList.add('sp-wave'); setTimeout(function() {{ pet.classList.remove('sp-wave'); }}, 1000); }}
                        }}
                        resetIdle();
                    }}, 250);
                }}

                // Drag
                function onDown(e) {{
                    if (e.button !== 0) return;
                    isDragging = true; dragMoved = false;
                    var r = pet.getBoundingClientRect();
                    startX = e.clientX; startY = e.clientY; origLeft = r.left; origTop = r.top;
                    pet.classList.add('sp-dragging');
                    pet.style.right = 'auto'; pet.style.bottom = 'auto';
                    pet.style.left = origLeft + 'px'; pet.style.top = origTop + 'px';
                    e.preventDefault();
                }}
                function onMove(e) {{
                    if (isDragging) {{
                        var dx = e.clientX - startX, dy = e.clientY - startY;
                        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragMoved = true;
                        var nl = origLeft + dx, nt = origTop + dy;
                        var vw = window.parent.innerWidth || doc.documentElement.clientWidth;
                        var vh = window.parent.innerHeight || doc.documentElement.clientHeight;
                        nl = Math.max(0, Math.min(nl, vw - 80)); nt = Math.max(0, Math.min(nt, vh - 80));
                        pet.style.left = nl + 'px'; pet.style.top = nt + 'px';
                        return;
                    }}
                    var eyes = pet.querySelectorAll('.sp-pet-eye-pupil');
                    if (eyes.length >= 2) {{
                        var pr = pet.getBoundingClientRect();
                        var cx = pr.left + pr.width/2, cy = pr.top + pr.height/2;
                        var ang = Math.atan2(e.clientY - cy, e.clientX - cx);
                        var dist = Math.min(2, Math.hypot(e.clientX - cx, e.clientY - cy) / 100);
                        var ox = Math.cos(ang) * dist, oy = Math.sin(ang) * dist * 0.6;
                        eyes.forEach(function(el) {{ el.style.transform = 'translate(' + ox + 'px,' + oy + 'px)'; }});
                    }}
                }}
                function onUp(e) {{
                    if (!isDragging) return;
                    isDragging = false; pet.classList.remove('sp-dragging');
                    try {{ localStorage.setItem(petId, JSON.stringify({{left: pet.style.left, top: pet.style.top}})); }} catch(err) {{}}
                    setTimeout(function() {{ if (!dragMoved) onClick(e); }}, 0);
                }}
                pet.addEventListener('mousedown', onDown);
                doc.addEventListener('mousemove', onMove);
                doc.addEventListener('mouseup', onUp);
                pet.addEventListener('touchstart', function(e) {{ var t = e.touches[0]; onDown({{clientX:t.clientX,clientY:t.clientY,button:0,preventDefault:function(){{}}}}); }}, {{passive:false}});
                doc.addEventListener('touchmove', function(e) {{ if (!isDragging) return; var t = e.touches[0]; onMove({{clientX:t.clientX,clientY:t.clientY}}); e.preventDefault(); }}, {{passive:false}});
                doc.addEventListener('touchend', function(e) {{ var t = e.changedTouches[0]; onUp({{clientX:t.clientX,clientY:t.clientY}}); }});

                // Restore position
                try {{
                    var s = JSON.parse(localStorage.getItem(petId) || 'null');
                    if (s && s.left && s.top) {{ pet.style.right = 'auto'; pet.style.bottom = 'auto'; pet.style.left = s.left; pet.style.top = s.top; }}
                }} catch(err) {{}}

                renderQuickItems();

                // Welcome animation
                setTimeout(function() {{ setMood('sp-happy', 1200); show(pick(ctxMsgs), 4000); resetIdle(); }}, 1000);
                // Auto-talk every 20s
                setInterval(function() {{
                    if (!bubble.classList.contains('sp-show') && !pet.classList.contains('sp-sleepy') && !quickPanelOpen) {{
                        show(pick(ctxMsgs), 3500); setMood('sp-wag', 800); resetIdle();
                    }}
                }}, 20000);

                return true;
            }}

            // Try init immediately, then use MutationObserver to catch DOM rebuilds
            if (!initPet()) {{
                var observer = new MutationObserver(function() {{
                    if (doc.getElementById('spPet') && !doc.getElementById('spPet').__spBound) {{
                        initPet();
                    }}
                }});
                observer.observe(doc.body, {{childList: true, subtree: true}});
                // Also retry periodically for 3 seconds
                var retries = 0;
                var retryTimer = setInterval(function() {{
                    retries++;
                    if (initPet() || retries > 15) clearInterval(retryTimer);
                }}, 200);
            }}
        }})();
        