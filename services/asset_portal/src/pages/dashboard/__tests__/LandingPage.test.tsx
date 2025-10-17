import { render, screen } from '@testing-library/react';
import { ChakraProvider } from '@chakra-ui/react';
import LandingPage from '../LandingPage';
import theme from '../../../theme';

describe('LandingPage', () => {
  it('renders activity items', () => {
    render(
      <ChakraProvider theme={theme}>
        <LandingPage />
      </ChakraProvider>
    );

    expect(screen.getByText(/Studio control center/i)).toBeInTheDocument();
    expect(screen.getByText(/Texture pack v12 submitted to Review Board/)).toBeInTheDocument();
  });
});
