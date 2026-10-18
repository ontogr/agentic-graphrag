import ThemedImage from '@theme/ThemedImage';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from './styles.module.css';

/** A diagram with a light and a dark version, picked by the site theme. */
export default function Diagram({name, alt, className, folder = 'readme'}) {
  return (
    <div className={styles.scroller}>
      <ThemedImage
        className={`${styles.diagram} ${className ?? ''}`}
        alt={alt}
        sources={{
          light: useBaseUrl(`/img/${folder}/${name}.png`),
          dark: useBaseUrl(`/img/${folder}/${name}-dark.png`),
        }}
      />
    </div>
  );
}
