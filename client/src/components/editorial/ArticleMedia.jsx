import { useEffect, useState } from 'react';
import { getArticleImage, getPlaceholderLabel } from '../../utils/articleMedia';

function youtubeFallback(src) {
  if (!src || typeof src !== 'string') return null;
  if (src.includes('maxresdefault.jpg')) {
    return src.replace('maxresdefault.jpg', 'hqdefault.jpg');
  }
  return null;
}

export default function ArticleMedia({
  article,
  className = '',
  alt,
  zoom = false,
  preferHero = false,
}) {
  const primary = getArticleImage(article, { preferHero });
  const [src, setSrc] = useState(primary);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setSrc(primary);
    setFailed(false);
    setLoaded(false);
  }, [primary]);

  const showImg = Boolean(src) && !failed;
  const label = getPlaceholderLabel(article);

  return (
    <div className={`relative overflow-hidden bg-primary/10 ${className}`}>
      {showImg && !loaded && (
        <div
          className="absolute inset-0 animate-pulse bg-gradient-to-br from-primary/15 via-primary/10 to-primary/5"
          aria-hidden="true"
        />
      )}

      {showImg ? (
        <img
          key={src}
          src={src}
          alt={alt || article?.title || ''}
          className={`absolute inset-0 h-full w-full object-cover object-center transition-all duration-300 ${
            loaded ? 'opacity-100' : 'opacity-0'
          } ${zoom ? 'group-hover:scale-105' : ''}`}
          loading="lazy"
          onLoad={(e) => {
            const img = e.currentTarget;
            // Soft-reject extreme portrait crops for hero surfaces
            if (
              preferHero &&
              img.naturalWidth > 0 &&
              img.naturalHeight > 0 &&
              img.naturalWidth / img.naturalHeight < 1.15
            ) {
              const next = youtubeFallback(src);
              if (next && next !== src) {
                setSrc(next);
                setLoaded(false);
                return;
              }
            }
            setLoaded(true);
          }}
          onError={() => {
            const next = youtubeFallback(src);
            if (next && next !== src) {
              setSrc(next);
              setLoaded(false);
              return;
            }
            setFailed(true);
            setLoaded(false);
          }}
        />
      ) : (
        <div
          className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-primary to-primary-hover text-white"
          aria-hidden="true"
        >
          <span className="text-3xl font-bold opacity-80">{label}</span>
        </div>
      )}
    </div>
  );
}
