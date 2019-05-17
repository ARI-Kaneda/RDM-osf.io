<%inherit file="notify_base.mako" />

<%def name="content()">
<tr>
  <td style="border-collapse: collapse;">
    Hello ${user.fullname},<br>
    <br>
    Thank you for registering for an account on the GakuNin RDM.<br>
    <br>
    Please verify your email address by visiting this link:<br>
    <br>
    ${confirmation_url}<br>
    <br>
    The GRDM Team<br>

</tr>
</%def>
