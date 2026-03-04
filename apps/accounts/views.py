from django.shortcuts import render, redirect
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from .forms import RegisterForm, ProfileUpdateForm


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Hello, {user.first_name}! Your account was successfully created.')
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def profile(request):
    user = request.user
    profile_obj = user.profile

    # Split into two forms: user info + profile info
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            # Update User fields
            user.first_name = request.POST.get('first_name', user.first_name).strip()
            user.last_name  = request.POST.get('last_name', user.last_name).strip()
            new_email       = request.POST.get('email', user.email).strip()
            from django.contrib.auth.models import User as U
            if new_email != user.email and U.objects.filter(email=new_email).exclude(pk=user.pk).exists():
                messages.error(request, 'This email is already in use.')
            else:
                user.email = new_email
                user.save()
                profile_obj.bio          = request.POST.get('bio', '').strip()
                profile_obj.organization = request.POST.get('organization', '').strip()
                profile_obj.job_title    = request.POST.get('job_title', '').strip()
                profile_obj.save()
                messages.success(request, 'Profile was updated successfully.')

        elif action == 'change_password':
            pw_form = PasswordChangeForm(user, request.POST)
            if pw_form.is_valid():
                pw_form.save()
                update_session_auth_hash(request, pw_form.user)
                messages.success(request, 'Password was changed successfully.')
            else:
                for field, errs in pw_form.errors.items():
                    for e in errs:
                        messages.error(request, e)

        elif action == 'update_notifications':
            profile_obj.notify_team_invites = bool(request.POST.get('notify_team_invites'))
            profile_obj.notify_comments     = bool(request.POST.get('notify_comments'))
            profile_obj.notify_weekly       = bool(request.POST.get('notify_weekly'))
            profile_obj.save()
            messages.success(request, 'Notification preferences were updated successfully.')

        return redirect('profile')

    from apps.projects.models import ProjectMember
    project_count    = ProjectMember.objects.filter(user=user).count()

    ctx = {
        'active_nav': 'profile',
        'profile_obj': profile_obj,
        'project_count': project_count,
        'pw_form': PasswordChangeForm(user),
    }
    return render(request, 'app/profile.html', ctx)
