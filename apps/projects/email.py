from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags


def send_invitation_email(invitation):
    subject = f"Invitation to join project {invitation.project.name}"
    context = {
        'invitation': invitation,
        'accept_url': settings.SITE_URL + f'/invite/{invitation.token}/accept/',
        'project_name': invitation.project.name,
        'inviter': invitation.invited_by.get_full_name() or invitation.invited_by.username,
    }
    html_message = render_to_string('email/invitation.html', context)
    plain_message = strip_tags(html_message)
    send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [invitation.email], html_message=html_message)


def send_workspace_invitation_email(invitation):
    subject = f"Invitation to join {invitation.workspace.name}"
    context = {
        'invitation': invitation,
        'accept_url': settings.SITE_URL + f'/invite/workspace/{invitation.token}/accept/',
        'workspace_name': invitation.workspace.name,
        'inviter': invitation.invited_by.get_full_name() or invitation.invited_by.username,
    }
    html_message = render_to_string('email/workspace_invitation.html', context)
    plain_message = strip_tags(html_message)
    send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [invitation.email], html_message=html_message)