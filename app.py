# tests/test_app.py
import pytest
import json
from app import app, db, User, Product

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    import os
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'test-key')
    app.config['JWT_SECRET'] = os.environ.get('JWT_SECRET', 'test-jwt')
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert data['version'] == '1.0.0'

def test_register_user(client):
    user_data = {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'password123'
    }
    response = client.post('/api/v1/users/register', 
                          data=json.dumps(user_data),
                          content_type='application/json')
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['message'] == 'User created successfully'
    assert data['user']['username'] == 'testuser'

def test_login_user(client):
    # First register a user
    user_data = {
        'username': 'logintest',
        'email': 'login@example.com',
        'password': 'password123'
    }
    client.post('/api/v1/users/register', 
               data=json.dumps(user_data),
               content_type='application/json')
    
    # Then login
    login_data = {
        'username': 'logintest',
        'password': 'password123'
    }
    response = client.post('/api/v1/users/login',
                          data=json.dumps(login_data),
                          content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'token' in data

def test_create_product_admin_only(client):
    # Create admin user first
    with app.app_context():
        admin = User(
            username='admin',
            email='admin@test.com',
            is_admin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
    
    # Login as admin
    login_response = client.post('/api/v1/users/login',
                                data=json.dumps({'username': 'admin', 'password': 'admin123'}),
                                content_type='application/json')
    token = json.loads(login_response.data)['token']
    
    # Create product
    product_data = {
        'name': 'Test Product',
        'price': 99.99,
        'stock': 10,
        'category': 'Electronics'
    }
    response = client.post('/api/v1/products',
                          data=json.dumps(product_data),
                          content_type='application/json',
                          headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['product']['name'] == 'Test Product'

def test_get_products(client):
    # Add some test products
    with app.app_context():
        product1 = Product(name='Product 1', price=10.0, stock=5)
        product2 = Product(name='Product 2', price=20.0, stock=3)
        db.session.add_all([product1, product2])
        db.session.commit()
    
    response = client.get('/api/v1/products')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data['products']) == 2

def test_rate_limiting(client):
    # Make multiple rapid requests to trigger rate limit
    for _ in range(6):  # Limit is 5 per minute
        response = client.post('/api/v1/users/register',
                              data=json.dumps({'username': f'user{_}', 'email': f'user{_}@test.com', 'password': 'pass'}),
                              content_type='application/json')
        if _ >= 5:
            assert response.status_code == 429  # Rate limit exceeded

def test_database_connection(client):
    response = client.get('/api/v1/test/db')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'Database connection successful' in data['status']

def test_cache_functionality(client):
    # Set cache
    response = client.post('/api/v1/test/cache?key=testkey&value=testvalue')
    assert response.status_code == 200
    
    # Get cache
    response = client.get('/api/v1/test/cache?key=testkey')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['value'] == 'testvalue'

def test_invalid_login(client):
    login_data = {
        'username': 'nonexistent',
        'password': 'wrongpassword'
    }
    response = client.post('/api/v1/users/login',
                          data=json.dumps(login_data),
                          content_type='application/json')
    assert response.status_code == 401

def test_unauthorized_access(client):
    response = client.get('/api/v1/users/profile')
    assert response.status_code == 401  # No token provided

if __name__ == '__main__':
    pytest.main()
