# Free deployment (Render, Neon, and Cloudinary)

The storefront and admin panel are part of the same Django application, so they
deploy together as one web service. Render's free service has temporary local
storage; this setup keeps database records in Neon and uploaded product images
in Cloudinary instead.

## Deploy

1. Push the project to a GitHub repository. Do not commit `.env` files,
   `db.sqlite3`, or production credentials.
2. Create a PostgreSQL project on [Neon](https://neon.tech/). Copy its connection
   string for Render's `DATABASE_URL` environment variable.
3. Create a [Cloudinary](https://cloudinary.com/) account. Copy its `CLOUDINARY_URL`
   from the account dashboard.
4. In Render, choose **New → Blueprint**, connect the repository, and deploy
   `render.yaml`. When prompted, provide the Neon connection string and
   Cloudinary URL. Render generates `DJANGO_SECRET_KEY` for the service.
5. After the first successful deploy, open the service's Shell and run
   `python manage.py createsuperuser`. Visit `/admin-panel/login/` on the deployed
   site and sign in with that account. The Django admin interface is not mounted
   at `/admin`.

The deploy command applies database migrations at startup. Static files are
collected during the build and served with WhiteNoise. Existing local products,
users, orders, and image files are not copied automatically: add products and
categories through the deployed admin panel, then upload their images there.

## Free-tier limitations

Render's free web service can sleep while idle, so the first request after a
period of inactivity may take longer. Its local filesystem is temporary, which
is why this project requires the external database and image storage in
production. Check current provider quotas and terms before relying on free
services for live orders or customer data.

For custom domains, add the hostname to Render's `ALLOWED_HOSTS` and set
`CSRF_TRUSTED_ORIGINS` to its HTTPS origin in the service environment.
