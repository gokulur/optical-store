(function hotReloadScript() {
    if (window.Shopify) {
        if (window.Shopify.isHotReloadInstalled)
            return;
        window.Shopify.isHotReloadInstalled = true;
    }
    const prefix = '[HotReload]';
    const logDebug = console.debug.bind(console, prefix);
    const logInfo = console.info.bind(console, prefix);
    const logError = console.error.bind(console, prefix);
    // Situations where this script can run:
    // - Local preview in the CLI: the URL is like localhost:<port>
    // - OSE visual preview: the URL is a myshopify.com domain
    // - Theme Preview: the URL is a myshopify.com domain
    const searchParams = new URLSearchParams(window.location.search);
    const isLocalPreview = Boolean(window.location.port);
    const isOSE = searchParams.has('oseid');
    if (isOSE && searchParams.get('source') === 'visualPreviewInitialLoad') {
        // OSE adds this extra iframe to the page and we don't need to hot reload it.
        return;
    }
    const hrParam = 'hr';
    const hrKey = `__${hrParam}`;
    const hrNavigationKey = `${hrKey}_navigation`;
    const safeCall = (fn) => {
        try {
            return fn();
        }
        catch (error) {
            console.error(error);
        }
    };
    if (isOSE && window.Shopify) {
        // OSE uses this information after navigating from a HotReload event.
        // Reset it here after it has been used:
        window.Shopify.isHotReloadNavigation =
            safeCall(() => sessionStorage.getItem(hrNavigationKey) === 'true') ??
                false;
        if (window.Shopify.isHotReloadNavigation) {
            window.addEventListener('load', () => {
                safeCall(() => sessionStorage.removeItem(hrNavigationKey));
                setTimeout(() => {
                    window.Shopify.isHotReloadNavigation = false;
                });
            });
        }
    }
    const waitForSFR = async () => {
        if (!isLocalPreview) {
            await new Promise((resolve) => setTimeout(resolve, 2000));
        }
    };
    const fullPageReload = async (key, error) => {
        if (error)
            logError(error);
        logInfo('Full reload:', key);
        if (isOSE && window.Shopify) {
            window.Shopify.isHotReloadNavigation = true;
            safeCall(() => sessionStorage.setItem(hrNavigationKey, 'true'));
        }
        if (!isLocalPreview) {
            if (isOSE)
                oseActions.sendEvent({ type: 'full' });
            await waitForSFR();
        }
        window.location.reload();
    };
    const refreshHTMLLinkElements = (elements) => {
        for (const element of elements) {
            // The `href` property prepends the host to the pathname. Use attributes instead.
            // Note: when a .liquid asset is requested but not found in SFR, it will be rendered as
            // `.../assets/file.css?1234` instead of `.../assets/file.css?v=1234`. Ensure we target both.
            element.setAttribute('href', (element.getAttribute('href') ?? '').replace(/(\?|&)(?:v=)?\d+$/, `$1v=${Date.now()}`));
        }
    };
    const buildSectionHotReloadUrl = (renderParams) => {
        const url = new URL(window.location.href);
        url.searchParams.set('_fd', '0');
        url.searchParams.set('pb', '0');
        for (const [key, value] of Object.entries(renderParams)) {
            if (value !== undefined) {
                url.searchParams.set(key, value);
            }
        }
        return url.toString();
    };
    const oseActions = {
        sendEvent: (payload) => {
            if (!isOSE)
                return;
            window.parent.postMessage({ type: 'StorefrontEvent::HotReload', payload }, `https://${window.Shopify.editorDomain}`);
        },
    };
    const refreshSections = async (data, elements) => {
        // The current section hot reload logic creates small issues in OSE state.
        // For now, we reload the full page to workaround this problem finding a better solution:
        if (isOSE)
            return fullPageReload(data.key);
        const controller = new AbortController();
        await Promise.all(elements.map(async (element) => {
            const sectionId = encodeURIComponent(element.id.replace(/^shopify-section-/, ''));
            const response = await fetch(buildSectionHotReloadUrl({
                section_id: sectionId,
                ...(isLocalPreview ? { section_key: data.key } : {}),
            }), { signal: controller.signal });
            if (!response.ok) {
                throw new Error(`Hot reload request failed: ${response.statusText}`);
            }
            const updatedSection = await response.text();
            if (element.parentNode) {
                element.outerHTML = updatedSection;
            }
        })).catch((error) => {
            controller.abort('Request error');
            fullPageReload(data.key, error);
        });
    };
    const refreshAppEmbedBlock = async (data, block) => {
        const controller = new AbortController();
        const appEmbedBlockId = encodeURIComponent(block.id.replace(/^shopify-block-/, ''));
        const response = await fetch(buildSectionHotReloadUrl({ app_block_id: appEmbedBlockId }), { signal: controller.signal });
        if (!response.ok) {
            const error = new Error(`Failed to fetch app block: ${response.statusText}`);
            controller.abort(error);
            return fullPageReload(data.key, error);
        }
        block.outerHTML = await response.text();
    };
    const refreshAppBlock = async (data, block) => {
        const blockSection = block.closest(`[id^=shopify-section-]`);
        const isAppEmbed = blockSection === null;
        if (isAppEmbed) {
            // App embed blocks rely on the app block rendering API to hot reload
            return refreshAppEmbedBlock(data, block);
        }
        else {
            // Regular section blocks rely on the section rendering API to hot reload
            return refreshSections(data, [blockSection]);
        }
    };
    const domActions = {
        updateSections: async (data) => {
            const elements = data.payload?.sectionNames?.flatMap((name) => Array.from(document.querySelectorAll(`[id^='shopify-section'][id$='${name}']`)));
            if (elements?.length) {
                await refreshSections(data, elements);
                logInfo(`Updated sections for "${data.key}":`, data.payload?.sectionNames);
            }
            else {
                // No sections found. Possible scenarios:
                // - The section is not used in the current page.
                // - The section has been removed.
                // - There's a Liquid syntax error in place of the section.
                // - This is a full error page.
                fullPageReload(data.key);
            }
        },
        updateCss: async (data, type) => {
            const hrefMatcher = data.key.endsWith('.liquid')
                ? data.key.replace(/^assets(\/[^\/]+).liquid$/, '$1')
                : `/${data.key}?`;
            const elements = Array.from(document.querySelectorAll(`link[rel="stylesheet"][href*="${hrefMatcher}"]`));
            refreshHTMLLinkElements(elements);
            logInfo(`Updated ${type} CSS: ${data.key}`);
        },
        updateExtAppBlock: async (data) => {
            const blockHandle = data.key.match(/\/(\w+)\.liquid$/)?.[1];
            const blockElements = Array.from(document.querySelectorAll(`[data-block-handle$='${blockHandle}']`));
            await Promise.all([
                blockElements.map((block) => {
                    return refreshAppBlock(data, block);
                }),
            ]);
            logInfo(`Updated blocks for ${data.key}`);
        },
    };
    let serverPid;
    const HOT_RELOAD_VERSION = '1';
    const onHotReloadEvent = async (event) => {
        logDebug('Event:', event);
        if (String(event.version) !== HOT_RELOAD_VERSION) {
            return logDebug(`Unknown event version "${event.version}"`);
        }
        if (!isLocalPreview &&
            String(event.themeId) !== String(window.Shopify?.theme?.id)) {
            return logDebug(`Theme ID mismatch. Event: "${event.themeId}" - Store: "${window.Shopify?.theme?.id}"`);
        }
        if (event.type === 'open') {
            serverPid ??= event.pid;
            // If the server PID is different it means that the process has been restarted.
            // Trigger a full-refresh to get all the latest changes.
            if (serverPid !== event.pid) {
                fullPageReload('Reconnected to new server');
            }
            return;
        }
        const [fileType] = event.key.split('/');
        if (event.type === 'full') {
            return fullPageReload(event.key);
        }
        if (event.type !== 'update' &&
            event.type !== 'delete' &&
            event.type !== 'create') {
            return logDebug(`Unknown event "${event.type}"`);
        }
        const isRemoteSync = event.sync === 'remote';
        // -- Theme App Extensions (TAE)
        if (event.payload?.isThemeExtension) {
            // App embed blocks come from local server. Skip remote sync:
            if (isRemoteSync)
                return;
            if (fileType === 'blocks')
                return domActions.updateExtAppBlock(event);
            if (fileType === 'assets' && event.key.endsWith('.css'))
                return domActions.updateCss(event, 'extension');
            return fullPageReload(event.key);
        }
        // -- Theme files
        if (fileType === 'assets') {
            const isLiquidAsset = event.key.endsWith('.liquid');
            const isCssAsset = event.key.endsWith('.css') || event.key.endsWith('.css.liquid');
            // Skip remote sync events for local preview unless it's a Liquid asset.
            // Skip local sync events for prod previews.
            if (isLocalPreview && !isLiquidAsset ? isRemoteSync : !isRemoteSync)
                return;
            if (isCssAsset) {
                if (isLiquidAsset && !isLocalPreview)
                    await waitForSFR();
                return domActions.updateCss(event, 'theme');
            }
            return fullPageReload(event.key);
        }
        // Config/schema files: no need to refresh preview.
        if (event.key === 'config/settings_schema.json' ||
            (fileType === 'locales' && event.key.endsWith('.schema.json'))) {
            return;
        }
        // -- Liquid files: check updated file parts.
        if (event.payload?.updatedFileParts && event.key.endsWith('.liquid')) {
            if (isLocalPreview && isRemoteSync)
                return;
            if (!isLocalPreview && !isRemoteSync)
                return;
            if (event.payload?.updatedFileParts?.javascriptTag ||
                event.payload?.updatedFileParts?.schemaTag) {
                return fullPageReload(event.key);
            }
            const willFullRefresh = event.payload?.updatedFileParts?.liquid !== false &&
                // Sections rely on the rendering API to hot reload
                (fileType !== 'sections' || isOSE);
            if (!willFullRefresh) {
                if (isOSE && !isRemoteSync)
                    return;
                if (event.payload?.updatedFileParts?.stylesheetTag !== false) {
                    if (!isLocalPreview)
                        await waitForSFR();
                    domActions.updateCss({ key: 'compiled_assets/styles.css' }, 'theme');
                }
                if (event.payload?.updatedFileParts?.liquid === false) {
                    return;
                }
            }
        }
        if (fileType === 'sections') {
            // Sections come from local server only in local preview:
            if (isLocalPreview ? isRemoteSync : !isRemoteSync)
                return;
            return domActions.updateSections(event);
        }
        // For other files, if there are replace templates, use local sync. Otherwise, wait for remote sync:
        const hasReplaceTemplates = Object.keys(event.payload?.replaceTemplates ?? {}).length > 0;
        if (isLocalPreview && hasReplaceTemplates ? !isRemoteSync : isRemoteSync) {
            return fullPageReload(event.key);
        }
    };
    // -- Connect to a hot reload event emitter:
    let hotReloadOrigin = window.location.origin;
    const hotReloadParam = searchParams.get(hrParam) ||
        window.location.port ||
        safeCall(() => localStorage.getItem(hrKey));
    // If an EventSource origin is specified, connect to it:
    if (hotReloadParam) {
        if (!isLocalPreview) {
            if (/^\d+$/.test(hotReloadParam)) {
                hotReloadOrigin = `http://localhost:${hotReloadParam}`;
            }
        }
        // Store the hot reload port in localStorage to keep it after a page reload,
        // but remove it from the URL to avoid confusing the user in Theme Preview.
        safeCall(() => localStorage.setItem(hrKey, hotReloadParam));
        if (!isLocalPreview && !isOSE && searchParams.has(hrParam)) {
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.delete(hrParam);
            window.history.replaceState({}, '', newUrl);
        }
        let hasEventSourceConnectedOnce = false;
        const evtSource = new EventSource(hotReloadOrigin);
        evtSource.onmessage = (event) => onHotReloadEvent(JSON.parse(event.data));
        evtSource.onopen = () => {
            hasEventSourceConnectedOnce = true;
            logInfo('Connected');
        };
        evtSource.onerror = (event) => {
            if (hasEventSourceConnectedOnce) {
                if (event.eventPhase === EventSource.CLOSED) {
                    logError('Connection closed by the server, attempting to reconnect...');
                }
                else {
                    logError('Error occurred, attempting to reconnect...');
                }
            }
            else {
                evtSource.close();
            }
        };
    }
    else if (!isOSE) {
        logInfo('CLI hot reload disabled - No hot reload port specified.');
    }
    // If this is embedded in an iframe (OSE) or an opened tab (Theme Preview from Code Editor),
    // start listening for hot reload events from the parent controller:
    if (window.self !== window.parent || window.opener) {
        window.addEventListener('message', (event) => {
            if (event.data?.type === 'StorefrontMessage::HotReload') {
                onHotReloadEvent(event.data.payload).catch((error) => logError('Error handling hot reload event from post message', error));
            }
        });
        if (isOSE) {
            oseActions.sendEvent({ type: 'open' });
        }
    }
})();
