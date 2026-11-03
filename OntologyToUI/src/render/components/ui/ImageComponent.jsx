export default function ImageComponent({ src, alt, width, height, alignment, borderRadius }) {
  return (
    <div style={{ textAlign: alignment || 'left', margin: '16px 0' }}>
      <img
        src={src}
        alt={alt || ''}
        style={{
          width: width || undefined,
          height: height || undefined,
          borderRadius: borderRadius || undefined,
          objectFit: 'contain',
        }}
      />
    </div>
  );
}
