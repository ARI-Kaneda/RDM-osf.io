<%inherit file="notify_base.mako" />

<%def name="content()">
<tr>
  <td style="border-collapse: collapse;">
    Hello ${user.fullname},<br>
    <br>
    Welcome to ${branded_preprints_provider}, powered by the GakuNin RDM. To continue, please verify your email address by visiting this link:<br>
    <br>
    ${confirmation_url}<br>
    <br>
    Sincerely yours,<br>
    <br>
    Your ${branded_preprints_provider} and GRDM teams<br>

</tr>
</%def>
