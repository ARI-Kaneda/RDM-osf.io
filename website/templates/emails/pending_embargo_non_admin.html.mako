<%inherit file="notify_base.mako" />

<%def name="content()">
<tr>
  <td style="border-collapse: collapse;">
    Hello ${user.fullname},<br>
    <br>
    We just wanted to let you know that ${initiated_by} has initiated an embargoed registration for the following pending registration: ${registration_link}.<br>
    <br>
    If approved, a registration will be created for the project, viewable here: ${registration_link}, and it will remain
    private until it is withdrawn, it is manually made public, or the embargo end date is passed on ${embargo_end_date.date()}.<br>
    <br>
    Sincerely yours,<br>
    <br>
    The GRDM Robots<br>

</tr>
</%def>
