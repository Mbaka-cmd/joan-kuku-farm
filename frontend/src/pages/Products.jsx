import { useState, useEffect } from 'react'
import axios from 'axios'
import './Products.css'

export default function Products() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    axios.get('http://localhost:8000/api/products/')
      .then(res => {
        console.log('API Response:', res.data)
        setProducts(res.data.results || res.data)
      })
      .catch(err => {
        console.error('API Error:', err)
        setError(err.message)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className='loading'>🔄 Loading products...</div>
  if (error) return <div className='error'>❌ Error: {error}</div>

  return (
    <div className='container'>
      <h1>🐔 Joan Kuku Farm</h1>
      <h2>Fresh Poultry Products</h2>
      <p className='count'>Total Products: {products.length}</p>
      {products.length === 0 ? (
        <p>No products found</p>
      ) : (
        <div className='grid'>
          {products.map(p => (
            <div key={p.id} className='card'>
              <h3>{p.name}</h3>
              <p className='price'>KES {p.price}</p>
              <p className='desc'>{p.description}</p>
              <p className='stock'>📦 Stock: {p.stock}</p>
              <button className='btn'>🛒 Add to Cart</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
