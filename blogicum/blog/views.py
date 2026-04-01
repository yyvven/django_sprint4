from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import UserChangeForm
from django.http import Http404, HttpResponse  # Добавьте HttpResponse
from django import forms
from blog.models import Post, Category, Comment

User = get_user_model()


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'text', 'pub_date', 'location', 'category', 'image']
        widgets = {
            'pub_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3}),
        }


def index(request):
    today = date.today()
    posts = (
        Post.objects.select_related("category")
        .filter(
            is_published=True,
            pub_date__lte=today,
            category__is_published=True,
        )
        .select_related("category", "location", "author")
        .order_by("-pub_date")
    )
    
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {"page_obj": page_obj}
    return render(request, "blog/index.html", context)


def category_posts(request, category_slug):
    today = date.today()
    category = get_object_or_404(
        Category,
        slug=category_slug,
        is_published=True,
    )
    posts = Post.objects.filter(
        category=category,
        is_published=True,
        pub_date__lte=today,
    ).select_related("category", "location", "author").order_by("-pub_date")
    
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        "page_obj": page_obj,
        "category": category,
    }
    return render(request, "blog/category.html", context)


def post_detail(request, id):
    today = date.today()
    
    post = get_object_or_404(Post, id=id)
    
    if request.user != post.author:
        post = get_object_or_404(
            Post,
            id=id,
            is_published=True,
            pub_date__lte=today,
            category__is_published=True,
        )
    
    comments = post.comments.all()
    form = CommentForm()
    context = {
        "post": post,
        "comments": comments,
        "form": form,
    }
    return render(request, "blog/detail.html", context)


@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('blog:profile', username=request.user.username)
    else:
        form = PostForm()
    
    return render(request, "blog/create.html", {'form': form})


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    if post.author != request.user:
        return redirect('blog:post_detail', id=post_id)
    
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            return redirect('blog:post_detail', id=post_id)
    else:
        form = PostForm(instance=post)
    
    return render(request, "blog/create.html", {'form': form, 'post': post})


@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    if post.author != request.user:
        return redirect('blog:post_detail', id=post_id)
    
    if request.method == 'POST':
        post.delete()
        return redirect('blog:index')
    
    return render(request, "blog/delete.html", {"post": post})


def profile(request, username):
    user = get_object_or_404(User, username=username)
    
    if request.user == user:
        posts = Post.objects.filter(
            author=user,
        ).order_by("-pub_date")
    else:
        posts = Post.objects.filter(
            author=user,
            category__is_published=True,
        ).order_by("-pub_date")
    
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        "profile": user,
        "page_obj": page_obj,
    }
    return render(request, "blog/profile.html", context)


@login_required
def edit_profile(request, username):
    user = get_object_or_404(User, username=username)
    
    if request.user != user:
        return redirect('blog:profile', username=username)
    
    if request.method == 'POST':
        form = UserChangeForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, user)
            return redirect('blog:profile', username=username)
    else:
        form = UserChangeForm(instance=user)
    
    return render(request, 'blog/edit_profile.html', {'form': form, 'profile': user})


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
    return redirect('blog:post_detail', id=post_id)


@login_required
def edit_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    
    if comment.author != request.user:
        raise Http404("Комментарий не найден")
    
    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            return redirect('blog:post_detail', id=post_id)
    else:
        form = CommentForm(instance=comment)
    
    # Используем существующий шаблон create.html
    return render(request, 'blog/create.html', {'form': form, 'post': comment.post})


@login_required
def delete_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    
    if comment.author != request.user:
        raise Http404("Комментарий не найден")
    
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', id=post_id)
    
    context = {
        'comment': comment,
        'post_id': post_id,
	'post': comment.post,
    }

    return render(request, 'blog/delete.html', context)
