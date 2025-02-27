<%inherit file="project/project_base.mako"/>
<%include file="util/render_grdm_addons_context.mako"/>
<%def name="title()">${node['title']} ${_("Files")}</%def>

<div class="page-header  visible-xs">
  <h2 class="text-300">${_("Files")}</h2>
</div>
% if not node['is_registration'] and not node['anonymous'] and permissions.WRITE in user['permissions']:
    <span class="f-w-xl">${_("Click on a storage provider or drag and drop to upload")}</span>
%endif

<!-- for fangorn.js: _createLinkEvent -->
<div id="link_container" style="display: none;">
    <input type="text"/>
</div>

<div id="treeGrid">
    <div class="ball-scale ball-scale-blue text-center m-v-xl"><div></div></div>
</div>

<%def name="stylesheets()">
    ${parent.stylesheets()}
    % for stylesheet in tree_css:
        <link rel='stylesheet' href='${stylesheet}' type='text/css' />
    % endfor
</%def>

<%def name="javascript_bottom()">
    ${parent.javascript_bottom()}
    % for script in tree_js:
        <script type="text/javascript" src="${script | webpack_asset}"></script>
    % endfor
    <script src=${"/static/public/js/files-page.js" | webpack_asset}></script>
    <script type="text/javascript">
        window.contextVars = window.contextVars || {};
        % if permissions.WRITE in user['permissions'] and not node['is_registration']:
            window.contextVars.diskSavingMode = !${ disk_saving_mode | sjson, n };
        % endif
        window.contextVars.analyticsMeta = $.extend(true, {}, window.contextVars.analyticsMeta, {
            pageMeta: {
                title: 'Files',
                public: true,
            },
        });
        window.contextVars.threshold = ${node['threshold']};
        window.contextVars.directory = {
            provider: ${ directory['provider'] if directory else False | sjson, n },
            path: ${ directory['path'] if directory else False | sjson, n },
            materializedPath: ${ directory['materializedPath'] if directory else False | sjson, n },
        };
    </script>
</%def>
