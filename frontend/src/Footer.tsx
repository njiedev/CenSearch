import AsciiImage from './AsciiImage'
import Logo from './Logo'
import alley from './assets/footer/alley.webm'

export default function Footer() {
  return (
    <footer className="site-footer">
      <AsciiImage src={alley} kind="video" focusX={0.5} focusY={1} />
      <div className="footer-content section-inner">
        <div className="footer-about">
          <a className="brand-link" href="#top" aria-label="CenSearch"><Logo /></a>
          <p>We find where your face ended up and get it taken down.</p>
          <p className="footer-credit">Built at Hack Midwest 2026.</p>
        </div>
        <nav className="footer-links" aria-label="Product">
          <h3>Product</h3>
          <a href="#mission">Mission</a>
          <a href="#features">Features</a>
          <a href="#faq">FAQ</a>
        </nav>
        <nav className="footer-links" aria-label="Start">
          <h3>Start</h3>
          <a href="/signup.html">Sign up</a>
        </nav>
      </div>
    </footer>
  )
}
