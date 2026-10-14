import AsciiImage from './AsciiImage'
import Logo from './Logo'
import alley from './assets/footer/alley.webm'

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-scene" aria-hidden="true">
        <AsciiImage src={alley} kind="video" focusX={0.5} focusY={0.8} />
      </div>
      <div className="footer-content section-inner">
        <div className="footer-about">
          <a className="brand-link" href="/#top" aria-label="CenSearch"><Logo /></a>
          <p>We find where your face ended up and get it taken down.</p>
          <p className="footer-credit">© 2026 CenSearch. Built at Hack Midwest.</p>
        </div>
        <nav className="footer-links" aria-label="Product">
          <h3>Product</h3>
          <a href="/#mission">Mission</a>
          <a href="/#features">Features</a>
          <a href="/signup/">Sign up</a>
        </nav>
        <nav className="footer-links" aria-label="Support">
          <h3>Support</h3>
          <a href="/#faq">FAQ</a>
          <a href="/contact/">Contact</a>
        </nav>
        <nav className="footer-links" aria-label="Legal">
          <h3>Legal</h3>
          <a href="/legal/privacy-policy/">Privacy Policy</a>
          <a href="/legal/terms-of-service/">Terms of Service</a>
        </nav>
      </div>
    </footer>
  )
}
