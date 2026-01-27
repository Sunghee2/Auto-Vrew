/**
 * Vrew 이미지 자동 삽입 스크립트
 * 브라우저 개발자 도구 콘솔(F12 → Console)에서 실행
 *
 * 사용법:
 * 1. Vrew 웹사이트에서 F12로 개발자 도구 열기
 * 2. Console 탭 선택
 * 3. 이 코드 전체를 복사해서 붙여넣기
 * 4. Enter로 실행
 */

(function() {
    'use strict';

    // ========== 설정 ==========
    // 이미지 파일 목록 (확장자 제외한 파일명)
    // 예: ['이미지1', '이미지2', '이미지3']
    const IMAGE_NAMES = [
        // 여기에 이미지 파일명 입력 (확장자 제외)
        // '검색할텍스트1',
        // '검색할텍스트2',
    ];

    // 대기 시간 (밀리초)
    const SHORT_WAIT = 500;
    const MEDIUM_WAIT = 1000;
    const LONG_WAIT = 2000;

    // ========== 유틸리티 함수 ==========
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function log(msg) {
        console.log(`[Vrew 자동화] ${msg}`);
    }

    // ========== 요소 찾기 함수 ==========

    // 검색 패널 열기 (Cmd+F 시뮬레이션)
    function openSearchPanel() {
        // 키보드 이벤트 시뮬레이션
        const event = new KeyboardEvent('keydown', {
            key: 'f',
            code: 'KeyF',
            metaKey: true,  // Cmd 키
            bubbles: true
        });
        document.dispatchEvent(event);
    }

    // 검색 입력창 찾기
    function findSearchInput() {
        // 여러 선택자 시도
        const selectors = [
            'input[placeholder*="검색"]',
            'input[placeholder*="찾기"]',
            '.search-input input',
            '.find-panel input',
            'input[type="search"]',
        ];

        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) return el;
        }

        // 모든 visible input 중 검색용 찾기
        const inputs = document.querySelectorAll('input[type="text"], input:not([type])');
        for (const inp of inputs) {
            if (inp.offsetParent !== null &&
                (inp.placeholder?.includes('검색') || inp.placeholder?.includes('찾기'))) {
                return inp;
            }
        }

        return null;
    }

    // 검색 결과 첫 번째 항목의 체크박스 찾기 (자막줄 탭)
    function findFirstSearchResultCheckbox() {
        // 검색 결과 내 체크박스 선택자
        const wrapper = document.querySelector('.searched-clip-wrapper');
        if (!wrapper) return null;

        // 체크박스 wrapper를 클릭해야 함 (role="checkbox" 요소 직접 클릭하면 안됨)
        // 클릭 가능한 wrapper 순서대로 시도
        const checkboxWrapperSelectors = [
            '.searched-clip-checkbox-wrapper',      // 체크박스 전체 wrapper
            '.vrew--checkbox-wrapper',              // Vrew 체크박스 wrapper
            '.vrew--checkbox',                      // Vrew 체크박스
            '.searched-clip-checkbox',              // 검색 결과 체크박스
        ];

        for (const sel of checkboxWrapperSelectors) {
            const checkboxWrapper = wrapper.querySelector(sel);
            if (checkboxWrapper && checkboxWrapper.offsetParent !== null) {
                return checkboxWrapper;
            }
        }

        // wrapper 못 찾으면 role="checkbox" 요소의 부모 찾기
        const roleCheckbox = wrapper.querySelector('[role="checkbox"]');
        if (roleCheckbox) {
            // 클릭 가능한 부모 wrapper 반환
            return roleCheckbox.closest('.vrew--checkbox') ||
                   roleCheckbox.closest('.searched-clip-checkbox-wrapper') ||
                   roleCheckbox.parentElement;
        }

        // 체크박스 못 찾으면 wrapper 자체 반환
        return wrapper;
    }

    // 검색 결과 첫 번째 항목 찾기 (자막줄 탭)
    function findFirstSearchResult() {
        // Vrew 자막줄 검색 결과 선택자
        const selectors = [
            '.searched-clip-wrapper',           // 자막줄 검색 결과 항목
            '.searched-clip-info-wrapper',      // 자막줄 클립 정보
            '.search-result-item',
            '.search-results li',
            '[class*="search-result"]',
            '[class*="find-result"]',
        ];

        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) return el;
        }

        return null;
    }

    // 클립 행 번호 찾기 (선택된 클립)
    function findSelectedClipRowNumber() {
        // 체크된/선택된 클립의 행 번호
        const selectors = [
            '.clip-main.checked .c-jtvrbl',
            '.clip-wrapper.selected .c-jtvrbl',
            '.c-jtvrbl.c-jtvrbl-fHayrg-selected-true',
        ];

        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) return el;
        }

        // 첫 번째 행 번호 반환
        return document.querySelector('.c-jtvrbl');
    }

    // 플로팅 메뉴의 삽입 버튼 찾기
    function findInsertButton() {
        // 플로팅 메뉴 내 삽입 버튼
        const floatingMenu = document.querySelector('.context-floating-menu');
        if (!floatingMenu) return null;

        // '삽입' 텍스트가 있는 요소
        const insertElements = floatingMenu.querySelectorAll('*');
        for (const el of insertElements) {
            if (el.textContent?.trim() === '삽입' ||
                el.textContent?.includes('삽입')) {
                // 클릭 가능한 부모 찾기
                let target = el;
                while (target && !target.onclick && target !== floatingMenu) {
                    target = target.parentElement;
                }
                return target || el;
            }
        }

        // data-tooltip으로 찾기
        return floatingMenu.querySelector('[data-tooltip*="삽입"]');
    }

    // PC에서 불러오기 버튼 찾기
    function findPCLoadButton() {
        // data-tooltip="PC에서 불러오기"
        let btn = document.querySelector('[data-tooltip="PC에서 불러오기"]');
        if (btn) return btn;

        // 플로팅 메뉴 내에서 찾기
        const floatingMenu = document.querySelector('.context-floating-menu');
        if (floatingMenu) {
            btn = floatingMenu.querySelector('.c-ijbaKvj');
            if (btn) return btn;
        }

        return null;
    }

    // 파일 input 찾기
    function findFileInput() {
        const inputs = document.querySelectorAll('input[type="file"]');
        // 이미지 관련 accept 속성 가진 것 우선
        for (const inp of inputs) {
            const accept = inp.getAttribute('accept') || '';
            if (accept.includes('image') || accept.includes('jpg') || accept.includes('png')) {
                return inp;
            }
        }
        return inputs[inputs.length - 1]; // 마지막 file input
    }

    // ========== 액션 함수 ==========

    // 검색 실행
    async function searchText(text) {
        log(`검색: "${text}"`);

        // 검색 패널 열기
        openSearchPanel();
        await sleep(MEDIUM_WAIT);

        // 검색 입력창 찾기
        const searchInput = findSearchInput();
        if (!searchInput) {
            log('검색 입력창을 찾을 수 없습니다.');
            return false;
        }

        // 포커스 및 기존 텍스트 삭제
        searchInput.focus();
        searchInput.select();
        await sleep(SHORT_WAIT);

        // 텍스트 입력
        searchInput.value = text;
        searchInput.dispatchEvent(new Event('input', { bubbles: true }));
        await sleep(SHORT_WAIT);

        // Enter 키로 검색
        searchInput.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            bubbles: true
        }));
        await sleep(MEDIUM_WAIT);

        return true;
    }

    // 요소를 실제 마우스 클릭처럼 클릭
    function simulateClick(element) {
        const rect = element.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        const mouseEvents = ['mousedown', 'mouseup', 'click'];
        for (const eventType of mouseEvents) {
            const event = new MouseEvent(eventType, {
                view: window,
                bubbles: true,
                cancelable: true,
                clientX: centerX,
                clientY: centerY,
            });
            element.dispatchEvent(event);
        }
    }

    // 첫 번째 검색 결과 클릭 (체크박스 선택)
    async function clickFirstResult() {
        log('첫 번째 검색 결과 체크박스 클릭');

        // 먼저 체크박스 wrapper를 클릭 시도
        const checkbox = findFirstSearchResultCheckbox();
        if (checkbox) {
            // 마우스 이벤트 시뮬레이션으로 클릭
            simulateClick(checkbox);
            await sleep(MEDIUM_WAIT);

            // 클릭 후 체크 상태 확인
            const roleCheckbox = checkbox.querySelector('[role="checkbox"]') ||
                                 checkbox.closest('.searched-clip-wrapper')?.querySelector('[role="checkbox"]');
            const isChecked = roleCheckbox?.getAttribute('aria-checked') === 'true' ||
                              checkbox.classList.contains('checked');
            log(`체크박스 선택 상태: ${isChecked ? '선택됨' : '선택 안됨'}`);

            // 선택 안됐으면 다시 시도
            if (!isChecked) {
                log('다시 클릭 시도...');
                checkbox.click();
                await sleep(MEDIUM_WAIT);
            }
            return true;
        }

        // 체크박스 못 찾으면 wrapper 클릭
        const result = findFirstSearchResult();
        if (result) {
            simulateClick(result);
            await sleep(MEDIUM_WAIT);
            return true;
        }

        // 검색 결과 없으면 Enter 키
        document.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            bubbles: true
        }));
        await sleep(MEDIUM_WAIT);
        return true;
    }

    // 행 번호 클릭 (플로팅 메뉴 표시)
    async function clickRowNumber() {
        log('행 번호 클릭');

        const row = findSelectedClipRowNumber();
        if (row) {
            row.click();
            await sleep(MEDIUM_WAIT);
            return true;
        }

        log('행 번호를 찾을 수 없습니다.');
        return false;
    }

    // 삽입 버튼 클릭
    async function clickInsertButton() {
        log('삽입 버튼 클릭');

        const btn = findInsertButton();
        if (btn) {
            btn.click();
            await sleep(SHORT_WAIT);
            return true;
        }

        log('삽입 버튼을 찾을 수 없습니다.');
        return false;
    }

    // PC에서 불러오기 클릭
    async function clickPCLoad() {
        log('PC에서 불러오기 클릭');

        const btn = findPCLoadButton();
        if (btn) {
            btn.click();
            await sleep(MEDIUM_WAIT);
            return true;
        }

        log('PC에서 불러오기 버튼을 찾을 수 없습니다.');
        return false;
    }

    // ========== 메인 로직 ==========

    async function processImage(imageName) {
        log(`처리 중: ${imageName}`);

        // 1. 검색
        if (!await searchText(imageName)) {
            log('검색 실패');
            return false;
        }

        // 2. 첫 번째 결과 클릭
        if (!await clickFirstResult()) {
            log('검색 결과 클릭 실패');
            return false;
        }

        // 3. 행 번호 클릭 (플로팅 메뉴 표시)
        await clickRowNumber();
        await sleep(SHORT_WAIT);

        // 4. 삽입 버튼 클릭
        if (!await clickInsertButton()) {
            log('삽입 버튼 클릭 실패');
            return false;
        }

        // 5. PC에서 불러오기 클릭
        if (!await clickPCLoad()) {
            log('PC에서 불러오기 클릭 실패');
            return false;
        }

        // 6. 파일 선택 대화상자가 열림 - 수동으로 파일 선택 필요
        log(`"${imageName}" 파일을 선택하세요!`);
        await sleep(LONG_WAIT);

        return true;
    }

    async function run() {
        log('===== Vrew 이미지 자동 삽입 시작 =====');

        if (IMAGE_NAMES.length === 0) {
            log('이미지 목록이 비어있습니다.');
            log('스크립트 상단의 IMAGE_NAMES 배열에 이미지 파일명을 추가하세요.');
            log('예: const IMAGE_NAMES = ["이미지1", "이미지2"];');
            return;
        }

        log(`처리할 이미지: ${IMAGE_NAMES.length}개`);

        let success = 0;
        let fail = 0;

        for (let i = 0; i < IMAGE_NAMES.length; i++) {
            const name = IMAGE_NAMES[i];
            log(`\n[${i + 1}/${IMAGE_NAMES.length}] ${name}`);

            try {
                if (await processImage(name)) {
                    success++;
                } else {
                    fail++;
                }
            } catch (e) {
                log(`오류: ${e.message}`);
                fail++;
            }

            // 다음 이미지 전 대기
            await sleep(LONG_WAIT);
        }

        log('\n===== 완료 =====');
        log(`성공: ${success}, 실패: ${fail}`);
    }

    // ========== 단일 이미지 처리 함수 (수동 호출용) ==========
    window.vrewInsertImage = async function(imageName) {
        if (!imageName) {
            log('사용법: vrewInsertImage("검색할텍스트")');
            return;
        }
        await processImage(imageName);
    };

    // ========== 실행 ==========
    if (IMAGE_NAMES.length > 0) {
        run();
    } else {
        log('===== Vrew 이미지 자동 삽입 스크립트 로드됨 =====');
        log('');
        log('사용법 1: 단일 이미지');
        log('  vrewInsertImage("검색할텍스트")');
        log('');
        log('사용법 2: 여러 이미지');
        log('  스크립트 상단의 IMAGE_NAMES 배열에 파일명 추가 후 다시 실행');
        log('');
    }

})();
